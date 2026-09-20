from __future__ import annotations
from difflib import SequenceMatcher
from app.core.schemas import CreatorDecision, TransferPlan, PlannedTransfer


def norm(s: str) -> str:
    return ''.join(ch.lower() for ch in s if ch.isalnum())


def resolve_player(name: str | None, players: list[dict]) -> dict | None:
    if not name:
        return None
    n = norm(name)
    scored = []
    for p in players:
        labels = [p.get('web_name', ''), p.get('first_name', '') + p.get('second_name', ''), p.get('second_name', '')]
        score = max(SequenceMatcher(None, n, norm(x)).ratio() for x in labels if x)
        scored.append((score, p))
    scored.sort(key=lambda x: x[0], reverse=True)
    return scored[0][1] if scored and scored[0][0] >= 0.72 else None


def exact_mirror(decision: CreatorDecision, team: dict, players: list[dict]) -> TransferPlan | None:
    if not decision.transfers:
        return None
    picks = {p['element']: p for p in team['picks']}
    bank = team['transfers']['bank']
    transfers: list[PlannedTransfer] = []
    delta = 0
    for t in decision.transfers:
        out_p = resolve_player(t.player_out, players)
        in_p = resolve_player(t.player_in, players)
        if not out_p or not in_p or out_p['id'] not in picks:
            return None
        out_pick = picks[out_p['id']]
        delta += int(out_pick['selling_price']) - int(in_p['now_cost'])
        transfers.append(PlannedTransfer(element_out=out_p['id'], element_in=in_p['id'], rationale='Exact creator mirror'))
    if bank + delta < 0:
        return None
    return TransferPlan(action='TRANSFER', confidence=0.99, mirrors_creator=True, intent_preserved=True, transfers=transfers, rationale='Exact creator decision is affordable.')


def candidate_pool(players: list[dict], team: dict, desired_names: list[str | None]) -> list[dict]:
    desired = {p['id'] for n in desired_names if (p := resolve_player(n, players))}
    by_type: dict[int, list[dict]] = {}
    for p in players:
        if p.get('status') not in ('a', 'd'):
            continue
        by_type.setdefault(p['element_type'], []).append(p)
    chosen: dict[int, dict] = {}
    for pid in desired:
        chosen[pid] = next(p for p in players if p['id'] == pid)
    for group in by_type.values():
        group.sort(key=lambda p: (float(p.get('form') or 0), p.get('total_points', 0)), reverse=True)
        for p in group[:35]:
            chosen[p['id']] = p
        cheap = sorted(group, key=lambda p: p['now_cost'])[:15]
        for p in cheap:
            chosen[p['id']] = p
    for pick in team['picks']:
        p = next((x for x in players if x['id'] == pick['element']), None)
        if p:
            chosen[p['id']] = p
    fields = ('id','web_name','team','element_type','now_cost','status','form','total_points','minutes','expected_goals','expected_assists','points_per_game')
    return [{k: p.get(k) for k in fields} for p in chosen.values()]
