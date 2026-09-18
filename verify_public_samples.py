#!/usr/bin/env python3
"""
Verification script for GridWise LLM:
Runs all 10 public sample cases against the optimization pipeline and prints a detailed score summary.
"""
import sys
import json
import asyncio
from pathlib import Path

from app.schemas import OptimizeEnergyRequest, BatteryConfig, HourEntry
from app.llm_interpreter import interpret_operator_notes
from app.guardrails import validate_and_guardrail_directives
from app.optimizer import solve_energy_schedule
from app.replay_validator import replay_and_validate_plan

SAMPLE_FILE = Path(__file__).resolve().parent / "BUP_CSE_FEST_2026_Preli_Public_Sample_Cases.json"

async def main():
    if not SAMPLE_FILE.exists():
        print(f"Error: Sample file not found at {SAMPLE_FILE}")
        sys.exit(1)

    with open(SAMPLE_FILE) as f:
        data = json.load(f)

    cases = data["cases"]
    print("=" * 80)
    print(f"  BUP CSE FEST 2026 - GridWise LLM Local Verification Suite")
    print(f"  Testing {len(cases)} Public Sample Cases")
    print("=" * 80)

    total_cases = len(cases)
    passed_cases = 0

    for i, case in enumerate(cases):
        cid = case["id"]
        label = case["label"]
        inp = case["input"]
        exp = case["expected_output"]

        print(f"\n[{i+1}/{total_cases}] Scenario {cid}: {label}")
        req = OptimizeEnergyRequest(
            scenario_id=inp["scenario_id"],
            operator_notes=inp["operator_notes"],
            hours=[HourEntry(**h) for h in inp["hours"]],
            battery=BatteryConfig(**inp["battery"])
        )

        # 1. Interpret & Guardrail
        raw_dirs = await interpret_operator_notes(req.operator_notes, req.battery)
        guarded_dirs = validate_and_guardrail_directives(raw_dirs, len(req.operator_notes), req.battery)

        # Check directive matches
        dir_match = True
        for g, e in zip(guarded_dirs, exp["directive_interpretation"]):
            if (g.directive_type != e["directive_type"] or
                g.applies != e["applies"] or
                g.structured_adjustment != e["structured_adjustment"]):
                dir_match = False
                print(f"    [!] Directive Mismatch: got {g.model_dump()} vs exp {e}")

        # 2. Solve Schedule
        plan = solve_energy_schedule(req.hours, req.battery, guarded_dirs)

        # 3. Replay Verification
        total_grid, total_cost, peak_grid, summary = replay_and_validate_plan(
            plan, req.hours, req.battery, guarded_dirs
        )

        cost_diff = abs(total_cost - exp["total_cost_bdt"])
        grid_diff = abs(total_grid - exp["total_grid_kwh"])
        peak_diff = abs(peak_grid - exp["peak_grid_kwh"])

        status = "PASSED" if (dir_match and cost_diff <= 0.01 and grid_diff <= 0.01) else "FAILED"
        if status == "PASSED":
            passed_cases += 1
            print(f"    [+] Status: {status}")
            print(f"        - Directives: 100% Match ({len(guarded_dirs)} items)")
            print(f"        - Grid Cost:  {total_cost:.2f} BDT (Expected: {exp['total_cost_bdt']:.2f} BDT, Diff: {cost_diff:.4f})")
            print(f"        - Grid Total: {total_grid:.2f} kWh (Expected: {exp['total_grid_kwh']:.2f} kWh, Diff: {grid_diff:.4f})")
            print(f"        - Grid Peak:  {peak_grid:.2f} kWh (Expected: {exp['peak_grid_kwh']:.2f} kWh, Diff: {peak_diff:.4f})")
        else:
            print(f"    [-] Status: {status}")

    print("\n" + "=" * 80)
    print(f"  Summary: {passed_cases}/{total_cases} Cases Passed ({passed_cases/total_cases*100:.1f}%)")
    print("=" * 80)
    if passed_cases == total_cases:
        print("  ALL CASES PASSED PERFECTLY!\n")
        sys.exit(0)
    else:
        print("  SOME CASES FAILED!\n")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
