from types import SimpleNamespace
from app.core.schemas import TransferPlan, PlannedTransfer
from app.services.validator import validate_plan


def test_valid_same_position_transfer():
    players = []
    # 2 GK, 5 DEF, 5 MID, 3 FWD across clubs
    types = [1,1,2,2,2,2,2,3,3,3,3,3,4,4,4]
    for i, typ in enumerate(types, 1):
        players.append({'id': i, 'element_type': typ, 'team': (i % 10)+1, 'now_cost': 50})
    players.append({'id': 99, 'element_type': 3, 'team': 15, 'now_cost': 55})
    picks = [{'element': i, 'selling_price': 50, 'purchase_price': 50} for i in range(1,16)]
    team = {'picks': picks, 'transfers': {'bank': 10, 'limit': 1, 'made': 0}}
    plan = TransferPlan(action='TRANSFER', confidence=.9, transfers=[PlannedTransfer(element_out=8, element_in=99, rationale='test')])
    s = SimpleNamespace(max_transfers_per_decision=3, allow_multi_transfer=True, allow_points_hits=False, max_points_hit=0)
    result = validate_plan(plan, team, players, s)
    assert result.ok, result.reason
