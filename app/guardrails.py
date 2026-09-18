import math
from typing import List, Dict, Any, Optional
from app.schemas import DirectiveInterpretation, BatteryConfig

ALLOWED_DIRECTIVES = {
    "solar_reduction",
    "minimum_battery_reserve",
    "no_charge_window",
    "no_discharge_window",
    "max_grid_window",
    "no_op"
}

def sanitize_hours(raw_hours: Any) -> List[int]:
    """Sanitize and sort hours: unique integers strictly in 0..23, ascending."""
    if not isinstance(raw_hours, list):
        return []
    valid = []
    for h in raw_hours:
        try:
            h_int = int(h)
            if 0 <= h_int <= 23:
                valid.append(h_int)
        except (ValueError, TypeError):
            continue
    return sorted(list(set(valid)))

def validate_and_guardrail_directives(
    raw_directives: List[Dict[str, Any]],
    num_notes: int,
    battery: BatteryConfig
) -> List[DirectiveInterpretation]:
    """
    Deterministically validate, sanitize, and guardrail raw directive interpretations
    against Section 08 rules.
    Guarantees:
    - Exactly num_notes entries.
    - Strict note_index order (0..num_notes-1).
    - Strict applies semantics: applies=False iff directive_type=='no_op'.
    - Valid numeric ranges and sorted unique hours.
    - Safe fallback to no_op for unrecognized or unparseable directives.
    """
    result: List[DirectiveInterpretation] = []
    
    # Map by note_index
    indexed_map = {}
    for d in raw_directives:
        if isinstance(d, dict) and "note_index" in d:
            try:
                idx = int(d["note_index"])
                if 0 <= idx < num_notes and idx not in indexed_map:
                    indexed_map[idx] = d
            except (ValueError, TypeError):
                pass

    for i in range(num_notes):
        raw = indexed_map.get(i)
        if not raw or not isinstance(raw, dict):
            # Fallback to no_op if missing
            result.append(
                DirectiveInterpretation(
                    note_index=i,
                    applies=False,
                    directive_type="no_op",
                    structured_adjustment=None,
                    explanation="No directive extracted or note is not applicable."
                )
            )
            continue

        raw_type = str(raw.get("directive_type", "no_op")).strip().lower()
        if raw_type not in ALLOWED_DIRECTIVES:
            raw_type = "no_op"

        explanation = str(raw.get("explanation", "")).strip()
        if not explanation:
            explanation = f"Directive {raw_type} interpretation."

        if raw_type == "no_op":
            result.append(
                DirectiveInterpretation(
                    note_index=i,
                    applies=False,
                    directive_type="no_op",
                    structured_adjustment=None,
                    explanation=explanation
                )
            )
            continue

        adj = raw.get("structured_adjustment")
        if not isinstance(adj, dict):
            # Invalid adjustment format, fallback to no_op safely
            result.append(
                DirectiveInterpretation(
                    note_index=i,
                    applies=False,
                    directive_type="no_op",
                    structured_adjustment=None,
                    explanation=explanation
                )
            )
            continue

        hours = sanitize_hours(adj.get("hours", []))
        if not hours:
            # An active directive with no valid hours is meaningless; fallback to no_op
            result.append(
                DirectiveInterpretation(
                    note_index=i,
                    applies=False,
                    directive_type="no_op",
                    structured_adjustment=None,
                    explanation=f"{explanation} (Fallback to no_op: no valid hours specified)"
                )
            )
            continue

        sanitized_adj: Optional[Dict[str, Any]] = None

        if raw_type == "solar_reduction":
            try:
                factor = float(adj.get("factor", 1.0))
                if math.isnan(factor) or math.isinf(factor):
                    factor = 1.0
                factor = max(0.0, min(1.0, factor))
            except (ValueError, TypeError):
                factor = 1.0
            sanitized_adj = {"hours": hours, "factor": round(factor, 4)}

        elif raw_type == "minimum_battery_reserve":
            try:
                min_energy = float(adj.get("minimum_energy_kwh", battery.minimum_energy_kwh))
                if math.isnan(min_energy) or math.isinf(min_energy):
                    min_energy = battery.minimum_energy_kwh
                min_energy = max(0.0, min(battery.capacity_kwh, min_energy))
            except (ValueError, TypeError):
                min_energy = battery.minimum_energy_kwh
            sanitized_adj = {"hours": hours, "minimum_energy_kwh": round(min_energy, 4)}

        elif raw_type == "no_charge_window":
            sanitized_adj = {"hours": hours}

        elif raw_type == "no_discharge_window":
            sanitized_adj = {"hours": hours}

        elif raw_type == "max_grid_window":
            try:
                max_grid = float(adj.get("max_grid_kwh", 0.0))
                if math.isnan(max_grid) or math.isinf(max_grid):
                    max_grid = 0.0
                max_grid = max(0.0, max_grid)
            except (ValueError, TypeError):
                max_grid = 0.0
            sanitized_adj = {"hours": hours, "max_grid_kwh": round(max_grid, 4)}

        result.append(
            DirectiveInterpretation(
                note_index=i,
                applies=True,
                directive_type=raw_type,
                structured_adjustment=sanitized_adj,
                explanation=explanation
            )
        )

    return result
