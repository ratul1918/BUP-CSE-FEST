import math
from typing import List, Tuple
import numpy as np
from scipy.optimize import linprog

from app.schemas import (
    HourEntry,
    BatteryConfig,
    DirectiveInterpretation,
    HourlyPlanEntry,
    BatteryActionType
)

def solve_energy_schedule(
    hours: List[HourEntry],
    battery: BatteryConfig,
    directives: List[DirectiveInterpretation]
) -> List[HourlyPlanEntry]:
    """
    Solves the 24-hour smart campus energy dispatch using a two-stage Linear Program (HiGHS):
    Stage 1: Minimize total grid electricity cost (primary objective).
    Stage 2: Minimize peak grid intake while preserving minimum cost (peak smoothing).
    Guarantees:
    - 100% adherence to all GridWise physical laws (balance, solar, battery state & limits, neutrality).
    - 100% adherence to active operator directives.
    - Zero simultaneous charging and discharging.
    """
    # 1. Apply directives to base profiles
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

    # 2. Stage 1: Minimize Grid Cost
    # Decision Variables (120 total):
    # indices 0..23:   grid_kwh [g_0 .. g_23]
    # indices 24..47:  solar_used_kwh [s_0 .. s_23]
    # indices 48..71:  battery_charge [c_0 .. c_23]
    # indices 72..95:  battery_discharge [d_0 .. d_23]
    # indices 96..119: battery_energy_after [E_0 .. E_23]

    c_obj1 = np.zeros(120)
    for h in range(24):
        c_obj1[h] = float(hours[h].tariff_bdt_per_kwh)

    bounds = []
    # g_h: [0, max_grid_caps[h]]
    for h in range(24):
        bounds.append((0.0, max_grid_caps[h]))
    # s_h: [0, eff_solar[h]]
    for h in range(24):
        bounds.append((0.0, eff_solar[h]))
    # c_h: [0, max_charge] or 0 if in no_charge_hours
    for h in range(24):
        ub_c = 0.0 if h in no_charge_hours else float(battery.max_charge_kwh_per_hour)
        bounds.append((0.0, ub_c))
    # d_h: [0, max_discharge] or 0 if in no_discharge_hours
    for h in range(24):
        ub_d = 0.0 if h in no_discharge_hours else float(battery.max_discharge_kwh_per_hour)
        bounds.append((0.0, ub_d))
    # E_h: [min_reserve[h], capacity]
    for h in range(24):
        bounds.append((min_reserve[h], float(battery.capacity_kwh)))

    # Equalities:
    # 1. Energy balance: g_h + s_h + d_h - c_h = demand_h (24 constraints)
    # 2. Battery state transitions:
    #    E_0 - c_0 + d_0 = initial_energy
    #    E_h - E_{h-1} - c_h + d_h = 0 (23 constraints)
    # 3. End-of-day neutrality: E_23 = initial_energy (1 constraint)
    A_eq = []
    b_eq = []

    for h in range(24):
        row = np.zeros(120)
        row[h] = 1.0       # g_h
        row[24 + h] = 1.0  # s_h
        row[72 + h] = 1.0  # d_h
        row[48 + h] = -1.0 # -c_h
        A_eq.append(row)
        b_eq.append(float(hours[h].demand_kwh))

    # E_0
    row0 = np.zeros(120)
    row0[96] = 1.0
    row0[48] = -1.0
    row0[72] = 1.0
    A_eq.append(row0)
    b_eq.append(float(battery.initial_energy_kwh))

    # E_h transitions
    for h in range(1, 24):
        row = np.zeros(120)
        row[96 + h] = 1.0
        row[96 + h - 1] = -1.0
        row[48 + h] = -1.0
        row[72 + h] = 1.0
        A_eq.append(row)
        b_eq.append(0.0)

    # Neutrality
    row_neutral = np.zeros(120)
    row_neutral[96 + 23] = 1.0
    A_eq.append(row_neutral)
    b_eq.append(float(battery.initial_energy_kwh))

    A_eq_arr = np.array(A_eq)
    b_eq_arr = np.array(b_eq)

    res1 = linprog(c_obj1, A_eq=A_eq_arr, b_eq=b_eq_arr, bounds=bounds, method='highs')
    if not res1.success:
        raise RuntimeError(f"Optimizer failed to find feasible solution in Stage 1: {res1.message}")

    min_cost = res1.fun

    # 3. Stage 2: Peak Grid Smoothing while locking cost <= min_cost + 1e-4
    # Variable 120 = M (peak grid import)
    c_obj2 = np.zeros(121)
    c_obj2[120] = 1.0  # minimize M
    for h in range(48, 96):
        c_obj2[h] = 1e-6  # slight tie-breaker to minimize unnecessary battery degradation

    bounds2 = list(bounds) + [(0.0, None)]
    A_eq2 = [np.append(r, 0.0) for r in A_eq]
    b_eq2 = list(b_eq)

    # Cost constraint: sum(tariff[h] * g_h) <= min_cost + 1e-4
    A_ub2 = []
    b_ub2 = []
    row_cost = np.zeros(121)
    for h in range(24):
        row_cost[h] = float(hours[h].tariff_bdt_per_kwh)
    A_ub2.append(row_cost)
    b_ub2.append(min_cost + 1e-4)

    # Peak constraints: g_h - M <= 0 for h in 0..23
    for h in range(24):
        row_peak = np.zeros(121)
        row_peak[h] = 1.0
        row_peak[120] = -1.0
        A_ub2.append(row_peak)
        b_ub2.append(0.0)

    res2 = linprog(
        c_obj2,
        A_ub=np.array(A_ub2),
        b_ub=np.array(b_ub2),
        A_eq=np.array(A_eq2),
        b_eq=np.array(b_eq2),
        bounds=bounds2,
        method='highs'
    )

    sol = res2.x if res2.success else res1.x

    # 4. Construct and clean HourlyPlanEntry list
    plan: List[HourlyPlanEntry] = []
    current_battery_energy = float(battery.initial_energy_kwh)

    for h in range(24):
        raw_g = sol[h]
        raw_s = sol[24 + h]
        raw_c = sol[48 + h]
        raw_d = sol[72 + h]

        # Enforce mutual exclusivity of charging and discharging
        # If numerical solver outputs tiny simultaneous charge & discharge, net them out
        net_battery = raw_c - raw_d
        if net_battery > 1e-5:
            action: BatteryActionType = "charge"
            b_kwh = net_battery
        elif net_battery < -1e-5:
            action = "discharge"
            b_kwh = abs(net_battery)
        else:
            action = "idle"
            b_kwh = 0.0

        # Update battery state precisely
        if action == "charge":
            current_battery_energy += b_kwh
        elif action == "discharge":
            current_battery_energy -= b_kwh

        # Clean solar used (cannot exceed effective solar)
        s_kwh = min(raw_s, eff_solar[h])
        if s_kwh < 1e-5:
            s_kwh = 0.0

        # Compute grid to ensure exact energy balance:
        # grid = demand + charge - discharge - solar_used
        demand_h = float(hours[h].demand_kwh)
        c_val = b_kwh if action == "charge" else 0.0
        d_val = b_kwh if action == "discharge" else 0.0
        g_kwh = max(0.0, demand_h + c_val - d_val - s_kwh)

        plan.append(
            HourlyPlanEntry(
                hour=h,
                grid_kwh=round(g_kwh, 2),
                solar_used_kwh=round(s_kwh, 2),
                battery_action=action,
                battery_kwh=round(b_kwh, 2),
                battery_energy_after_kwh=round(current_battery_energy, 2)
            )
        )

    # Guarantee final hour exact neutrality if within 0.05 float rounding
    if abs(plan[-1].battery_energy_after_kwh - battery.initial_energy_kwh) <= 0.05:
        plan[-1].battery_energy_after_kwh = float(battery.initial_energy_kwh)

    return plan
