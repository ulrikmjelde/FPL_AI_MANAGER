from __future__ import annotations
from dataclasses import dataclass
from app.core.config import Settings
from app.core.schemas import TransferPlan


@dataclass
class ValidationResult:
    ok: bool
    reason: str
    payload_transfers: list[dict]


def validate_plan(plan: TransferPlan, team: dict, players: list[dict], settings: Settings) -> ValidationResult:
    if plan.action != 'TRANSFER' or not plan.transfers:
        return ValidationResult(False, 'No transfer action', [])
    if len(plan.transfers) > settings.max_transfers_per_decision:
        return ValidationResult(False, 'Too many transfers for policy', [])
    if not settings.allow_multi_transfer and len(plan.transfers) > 1:
        return ValidationResult(False, 'Multi-transfer solutions disabled', [])

    by_id = {p['id']: p for p in players}
    picks = {p['element']: dict(p) for p in team['picks']}
    original_ids = set(picks)
    bank = int(team['transfers']['bank'])
    payload = []

    for t in plan.transfers:
        if t.element_out not in picks:
            return ValidationResult(False, f'Outgoing player {t.element_out} not in current squad', [])
        if t.element_in in original_ids or t.element_in in picks:
            return ValidationResult(False, f'Incoming player {t.element_in} already owned', [])
        outgoing = by_id.get(t.element_out)
        incoming = by_id.get(t.element_in)
        if not outgoing or not incoming:
            return ValidationResult(False, 'Unknown player id', [])
        if outgoing['element_type'] != incoming['element_type']:
            return ValidationResult(False, 'Transfers must preserve FPL position', [])
        out_pick = picks.pop(t.element_out)
        sell = int(out_pick['selling_price'])
        buy = int(incoming['now_cost'])
        bank += sell - buy
        if bank < 0:
            return ValidationResult(False, 'Insufficient budget', [])
        picks[t.element_in] = {'element': t.element_in, 'selling_price': buy, 'purchase_price': buy}
        payload.append({'element_out': t.element_out, 'element_in': t.element_in, 'selling_price': sell, 'purchase_price': buy})

    clubs: dict[int, int] = {}
    positions: dict[int, int] = {}
    for pid in picks:
        p = by_id[pid]
        clubs[p['team']] = clubs.get(p['team'], 0) + 1
        positions[p['element_type']] = positions.get(p['element_type'], 0) + 1
    if any(n > 3 for n in clubs.values()):
        return ValidationResult(False, 'More than 3 players from one club', [])
    if positions != {1: 2, 2: 5, 3: 5, 4: 3}:
        return ValidationResult(False, f'Invalid squad position counts: {positions}', [])

    transfers_state = team.get('transfers', {})
    limit = transfers_state.get('limit')
    made = transfers_state.get('made', 0)
    free = max(0, limit - made) if isinstance(limit, int) else None
    paid = max(0, len(plan.transfers) - free) if free is not None else 0
    hit = paid * 4
    if hit and (not settings.allow_points_hits or hit > settings.max_points_hit):
        return ValidationResult(False, f'Plan implies {-hit} point hit, outside policy', [])

    return ValidationResult(True, 'Valid', payload)
