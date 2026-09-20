from __future__ import annotations
import asyncio
import hashlib
from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from app.core.config import Settings
from app.db.base import SourceItem, Decision
from app.db.session import SessionLocal
from app.services.x_client import XClient
from app.services.youtube import extract_video_id, fetch_transcript
from app.services.fpl_client import FPLClient
from app.services.ai_brain import AIBrain
from app.services.planner import exact_mirror, candidate_pool
from app.services.validator import validate_plan
from app.services.notifier import notify


def fingerprint(payload: dict) -> str:
    import json
    canonical = json.dumps(payload, sort_keys=True, separators=(',', ':'))
    return hashlib.sha256(canonical.encode()).hexdigest()


def compact_squad(team: dict, players: list[dict]) -> list[dict]:
    by_id = {p['id']: p for p in players}
    out = []
    for pick in team['picks']:
        p = by_id[pick['element']]
        out.append({
            'id': p['id'], 'web_name': p['web_name'], 'team': p['team'],
            'element_type': p['element_type'], 'now_cost': p['now_cost'],
            'selling_price': pick['selling_price'], 'purchase_price': pick['purchase_price'],
            'status': p.get('status'), 'form': p.get('form'), 'total_points': p.get('total_points'),
        })
    return out


def state_signature(team: dict) -> tuple:
    return (
        tuple(sorted((p['element'], p.get('selling_price')) for p in team['picks'])),
        team.get('transfers', {}).get('bank'),
        team.get('transfers', {}).get('made'),
    )


class Monitor:
    def __init__(self, settings: Settings):
        self.s = settings
        self.x = XClient(settings.x_bearer_token)
        self.fpl = FPLClient(settings)
        self.ai = AIBrain(settings.openai_api_key, settings.openai_model)
        self._x_user_id: str | None = None

    async def run_once(self) -> dict:
        if not self._x_user_id:
            self._x_user_id = await self.x.user_id(self.s.x_creator_username)

        async with SessionLocal() as db:
            q = await db.execute(select(SourceItem).where(SourceItem.source == 'x').order_by(SourceItem.id.desc()).limit(1))
            last = q.scalar_one_or_none()
            posts = await self.x.latest_posts(self._x_user_id, last.external_id if last else None)

        if not last and posts and not self.s.process_initial_history:
            newest = posts[0]
            created = datetime.fromisoformat(newest['created_at'].replace('Z', '+00:00')) if newest.get('created_at') else datetime.now(timezone.utc)
            baseline = SourceItem(source='x', external_id=str(newest['id']), text=self._source_text(newest), url=f'https://x.com/{self.s.x_creator_username}/status/{newest["id"]}', created_at=created, processed=True)
            async with SessionLocal() as db:
                db.add(baseline)
                try:
                    await db.commit()
                except IntegrityError:
                    await db.rollback()
            return {'fetched': len(posts), 'processed': 0, 'baselined_at': newest['id']}

        processed = 0
        for post in reversed(posts):
            if await self.process_post(post):
                processed += 1
        return {'fetched': len(posts), 'processed': processed}

    @staticmethod
    def _source_text(post: dict) -> str:
        text = post.get('text', '')
        urls = [u.get('expanded_url') for u in post.get('entities', {}).get('urls', []) if u.get('expanded_url')]
        if urls:
            text += '\n' + '\n'.join(urls)
        return text

    async def process_post(self, post: dict) -> bool:
        created = datetime.fromisoformat(post['created_at'].replace('Z', '+00:00')) if post.get('created_at') else datetime.now(timezone.utc)
        item = SourceItem(source='x', external_id=str(post['id']), text=self._source_text(post), url=f'https://x.com/{self.s.x_creator_username}/status/{post["id"]}', created_at=created)
        async with SessionLocal() as db:
            db.add(item)
            try:
                await db.commit(); await db.refresh(item)
            except IntegrityError:
                await db.rollback(); return False

        transcript = None
        vid = extract_video_id(item.text)
        if vid and self.s.youtube_transcripts:
            transcript = await asyncio.to_thread(fetch_transcript, vid)

        decision = await self.ai.interpret(item.text, transcript)
        fp_payload = {
            'creator': self.s.x_creator_username,
            'classification': decision.classification,
            'transfers': [t.model_dump() for t in decision.transfers],
            'intent': decision.intent,
        }
        fp = fingerprint(fp_payload)
        row = Decision(
            source_item_id=item.id, classification=decision.classification,
            source_confidence=decision.source_confidence, ai_confidence=decision.ai_confidence,
            payload=decision.model_dump(), fingerprint=fp, executed=False,
            created_at=datetime.now(timezone.utc),
        )
        async with SessionLocal() as db:
            db.add(row)
            try:
                await db.commit(); await db.refresh(row)
            except IntegrityError:
                await db.rollback(); return True

        if decision.classification != 'CONFIRMED':
            return True
        if decision.source_confidence < self.s.min_source_confidence or decision.ai_confidence < self.s.min_ai_confidence:
            await notify(self.s.notify_webhook_url, f'FPL Shadow: confirmed-looking post withheld due to confidence. {item.url}')
            return True

        bootstrap = await self.fpl.bootstrap()
        players = bootstrap['elements']
        team_before = await self.fpl.my_team()
        plan = exact_mirror(decision, team_before, players)
        if not plan:
            desired = [t.player_in for t in decision.transfers]
            candidates = candidate_pool(players, team_before, desired)
            tr = team_before.get('transfers', {})
            limit, made = tr.get('limit'), tr.get('made', 0)
            free = max(0, limit - made) if isinstance(limit, int) else None
            policy = {
                'allow_alternative_players': self.s.allow_alternative_players,
                'allow_multi_transfer': self.s.allow_multi_transfer,
                'allow_points_hits': self.s.allow_points_hits,
                'max_points_hit': self.s.max_points_hit,
                'max_transfers_per_decision': self.s.max_transfers_per_decision,
                'auto_use_chips': self.s.auto_use_chips,
            }
            plan = await self.ai.plan(decision=decision, squad=compact_squad(team_before, players), candidates=candidates, policy=policy, bank=tr['bank'], free_transfers=free)

        if plan.confidence < self.s.min_ai_confidence:
            await notify(self.s.notify_webhook_url, f'FPL Shadow: transfer plan withheld at confidence {plan.confidence:.2f}. {item.url}')
            return True

        valid = validate_plan(plan, team_before, players, self.s)
        if not valid.ok:
            await notify(self.s.notify_webhook_url, f'FPL Shadow: plan rejected: {valid.reason}. {item.url}')
            return True

        result = {'plan': plan.model_dump(), 'validation': valid.reason, 'auto_transfer': self.s.auto_transfer}
        if self.s.auto_transfer:
            team_precommit = await self.fpl.my_team()
            if state_signature(team_precommit) != state_signature(team_before):
                result['status'] = 'ABORTED_STATE_CHANGED'
            else:
                valid2 = validate_plan(plan, team_precommit, players, self.s)
                if not valid2.ok:
                    result['status'] = f'ABORTED_REVALIDATION: {valid2.reason}'
                else:
                    event = next((e['id'] for e in bootstrap['events'] if e.get('is_next')), None) or next((e['id'] for e in bootstrap['events'] if e.get('is_current')), None)
                    api_result = await self.fpl.make_transfers(event=event, transfers=valid2.payload_transfers)
                    team_after = await self.fpl.my_team()
                    result.update({'status': 'EXECUTED', 'api_result': api_result, 'verified_team_signature': str(state_signature(team_after))})
                    row.executed = True
        else:
            result['status'] = 'DRY_RUN'

        row.execution_result = result
        async with SessionLocal() as db:
            await db.merge(row)
            await db.commit()
        await notify(self.s.notify_webhook_url, f'FPL Shadow: {result["status"]} — {plan.rationale} — {item.url}')
        return True
