import math
from typing import List, Tuple
from app.schemas import (
    HourEntry,
    BatteryConfig,
    DirectiveInterpretation,
    HourlyPlanEntry
)

def replay_and_validate_plan(
    plan: List[HourlyPlanEntry],
    hours: List[HourEntry],
    battery: BatteryConfig,
    directives: List[DirectiveInterpretation],
    tolerance: float = 0.02
) -> Tuple[float, float, float, str]:
    """
    Independently re-simulates the hourly_plan against all physical and directive rules.
    Verifies:
    1. 24 sequential hours 0..23.
    2. Non-negative, finite numbers.
    3. Battery transitions, bounds, and rate limits.
    4. Directive constraints (solar reduction, reserves, windows, grid caps).
    5. Hourly energy balance.
    6. End-of-day battery neutrality.
    
    Returns:
    (total_grid_kwh, total_cost_bdt, peak_grid_kwh, plan_summary)
    """
    if len(plan) != 24:
        raise ValueError(f"hourly_plan must contain exactly 24 entries, got {len(plan)}")

    # Precompute effective solar and directive limits
    eff_solar = [float(h.solar_kwh) for h in hours]
    min_reserve = [float(battery.minimum_energy_kwh)] * 24
    no_charge_hours = set()
    no_discharge_hours = set()
    max_grid_caps = [float('inf')] * 24

    for d in directives:
        if not d.applies or not d.structured_adjustment:
            continue
        dtype = d.directive_type
        adj = d.structured_adjustment
        adj_hours = adj.get("hours", [])

        if dtype == "solar_reduction":
            factor = float(adj.get("factor", 1.0))
            for h in adj_hours:
                eff_solar[h] = eff_solar[h] * factor
        elif dtype == "minimum_battery_reserve":
            req_min = float(adj.get("minimum_energy_kwh", battery.minimum_energy_kwh))
            for h in adj_hours:
                min_reserve[h] = max(min_reserve[h], req_min)
        elif dtype == "no_charge_window":
            for h in adj_hours:
                no_charge_hours.add(h)
        elif dtype == "no_discharge_window":
            for h in adj_hours:
                no_discharge_hours.add(h)
        elif dtype == "max_grid_window":
            grid_cap = float(adj.get("max_grid_kwh", float('inf')))
            for h in adj_hours:
                max_grid_caps[h] = min(max_grid_caps[h], grid_cap)

    prev_energy = float(battery.initial_energy_kwh)
    total_grid_kwh = 0.0
    total_cost_bdt = 0.0
    peak_grid_kwh = 0.0

    applied_descriptions = []

    for h, entry in enumerate(plan):
        if entry.hour != h:
            raise ValueError(f"Plan entry at index {h} has unexpected hour {entry.hour}")

        g = entry.grid_kwh
        s = entry.solar_used_kwh
        action = entry.battery_action
        b_kwh = entry.battery_kwh
        e_after = entry.battery_energy_after_kwh
        demand = float(hours[h].demand_kwh)
        tariff = float(hours[h].tariff_bdt_per_kwh)

        # Check non-negative finite
        for val, name in [(g, "grid_kwh"), (s, "solar_used_kwh"), (b_kwh, "battery_kwh"), (e_after, "battery_energy_after_kwh")]:
            if math.isnan(val) or math.isinf(val) or val < -tolerance:
                raise ValueError(f"Hour {h}: invalid {name}={val}")

        # Check solar limit
        if s > eff_solar[h] + tolerance:
            raise ValueError(f"Hour {h}: solar_used ({s}) exceeds effective solar ({eff_solar[h]})")

        # Check battery action & rate limits
        if action == "charge":
            if h in no_charge_hours and b_kwh > tolerance:
                raise ValueError(f"Hour {h}: battery charged during no_charge_window")
            if b_kwh > battery.max_charge_kwh_per_hour + tolerance:
                raise ValueError(f"Hour {h}: charge rate {b_kwh} exceeds max {battery.max_charge_kwh_per_hour}")
            expected_e = prev_energy + b_kwh
        elif action == "discharge":
            if h in no_discharge_hours and b_kwh > tolerance:
                raise ValueError(f"Hour {h}: battery discharged during no_discharge_window")
            if b_kwh > battery.max_discharge_kwh_per_hour + tolerance:
                raise ValueError(f"Hour {h}: discharge rate {b_kwh} exceeds max {battery.max_discharge_kwh_per_hour}")
            expected_e = prev_energy - b_kwh
        elif action == "idle":
            if b_kwh > tolerance:
                raise ValueError(f"Hour {h}: idle battery action must have battery_kwh = 0")
            expected_e = prev_energy
        else:
            raise ValueError(f"Hour {h}: invalid battery action '{action}'")

        # Check state transition
        if abs(e_after - expected_e) > tolerance:
            raise ValueError(f"Hour {h}: state transition error. Expected {expected_e}, got {e_after}")

        # Check battery bounds & reserves
        if e_after > battery.capacity_kwh + tolerance:
            raise ValueError(f"Hour {h}: battery energy {e_after} exceeds capacity {battery.capacity_kwh}")
        if e_after < min_reserve[h] - tolerance:
            raise ValueError(f"Hour {h}: battery energy {e_after} below required minimum reserve {min_reserve[h]}")

        # Check grid cap
        if g > max_grid_caps[h] + tolerance:
            raise ValueError(f"Hour {h}: grid import {g} exceeds max_grid cap {max_grid_caps[h]}")

        # Check energy balance: grid + solar_used + discharge = demand + charge
        charge_amt = b_kwh if action == "charge" else 0.0
        discharge_amt = b_kwh if action == "discharge" else 0.0
        supply = g + s + discharge_amt
        consumption = demand + charge_amt
        if abs(supply - consumption) > tolerance:
            raise ValueError(f"Hour {h}: energy balance violated. Supply={supply}, Demand={consumption}, Diff={abs(supply-consumption)}")

        total_grid_kwh += g
        total_cost_bdt += g * tariff
        if g > peak_grid_kwh:
            peak_grid_kwh = g

        prev_energy = e_after

    # Check End-of-Day Neutrality
    if abs(prev_energy - battery.initial_energy_kwh) > tolerance:
        raise ValueError(
            f"End-of-day battery neutrality violated. Final {prev_energy} != Initial {battery.initial_energy_kwh}"
        )

    # Build descriptive plan_summary
    active_directives = [d for d in directives if d.applies]
    if active_directives:
        dir_names = [d.directive_type.replace("_", " ") for d in active_directives]
        summary_str = (
            f"Successfully applied {len(active_directives)} directive(s) ({', '.join(dir_names)}). "
            f"Optimized 24-hour battery scheduling around tariff peaks to minimize total grid cost "
            f"while strictly respecting all reserves, windows, rate limits, and end-of-day battery neutrality."
        )
    else:
        summary_str = (
            "No active operational directives required adjustment. "
            "Optimized 24-hour battery charge/discharge schedule against grid tariffs while "
            "maintaining full energy balance and restoring initial battery storage level."
        )

    return (
        round(total_grid_kwh, 2),
        round(total_cost_bdt, 2),
        round(peak_grid_kwh, 2),
        summary_str
    )
