import json
import pytest
import asyncio
from pathlib import Path

from app.schemas import (
    OptimizeEnergyRequest,
    BatteryConfig,
    HourEntry
)
from app.llm_interpreter import interpret_operator_notes
from app.guardrails import validate_and_guardrail_directives
from app.optimizer import solve_energy_schedule
from app.replay_validator import replay_and_validate_plan

SAMPLE_FILE = Path(__file__).resolve().parent.parent / "BUP_CSE_FEST_2026_Preli_Public_Sample_Cases.json"

@pytest.fixture(scope="module")
def sample_data():
    with open(SAMPLE_FILE) as f:
        return json.load(f)["cases"]

def test_all_10_sample_cases(sample_data):
    """
    Iterate over each public sample case:
    1. Parse request object.
    2. Run interpretation & guardrails.
    3. Verify directives match organizer ground truth.
    4. Run LP optimizer.
    5. Run replay validator.
    6. Verify total_cost_bdt matches reference optimal cost within 0.01 BDT.
    7. Verify total_grid_kwh matches reference within 0.01 kWh.
    """
    async def _run():
        for case in sample_data:
            case_id = case["id"]
            inp = case["input"]
            exp = case["expected_output"]

            req = OptimizeEnergyRequest(
                scenario_id=inp["scenario_id"],
                operator_notes=inp["operator_notes"],
                hours=[HourEntry(**h) for h in inp["hours"]],
                battery=BatteryConfig(**inp["battery"])
            )

            # 1. Interpret
            raw_dirs = await interpret_operator_notes(req.operator_notes, req.battery)
            guarded_dirs = validate_and_guardrail_directives(raw_dirs, len(req.operator_notes), req.battery)

            # 2. Check directive semantics against ground truth
            assert len(guarded_dirs) == len(exp["directive_interpretation"])
            for g, e in zip(guarded_dirs, exp["directive_interpretation"]):
                assert g.directive_type == e["directive_type"], f"{case_id} type mismatch"
                assert g.applies == e["applies"], f"{case_id} applies mismatch"
                assert g.structured_adjustment == e["structured_adjustment"], f"{case_id} adjustment mismatch"

            # 3. Optimize
            plan = solve_energy_schedule(req.hours, req.battery, guarded_dirs)
            assert len(plan) == 24

            # 4. Replay Validate
            total_grid, total_cost, peak_grid, summary = replay_and_validate_plan(
                plan, req.hours, req.battery, guarded_dirs
            )

            # 5. Check optimal cost matches reference
            cost_diff = abs(total_cost - exp["total_cost_bdt"])
            assert cost_diff <= 0.01, f"{case_id}: cost diff {cost_diff} exceeds 0.01 BDT (got {total_cost}, exp {exp['total_cost_bdt']})"

            # 6. Check total grid matches reference
            grid_diff = abs(total_grid - exp["total_grid_kwh"])
            assert grid_diff <= 0.01, f"{case_id}: grid diff {grid_diff} exceeds 0.01 kWh (got {total_grid}, exp {exp['total_grid_kwh']})"

    asyncio.run(_run())
