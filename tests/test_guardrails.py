import pytest
from app.schemas import BatteryConfig
from app.guardrails import validate_and_guardrail_directives, sanitize_hours

@pytest.fixture
def sample_battery():
    return BatteryConfig(
        capacity_kwh=500.0,
        initial_energy_kwh=200.0,
        minimum_energy_kwh=50.0,
        max_charge_kwh_per_hour=100.0,
        max_discharge_kwh_per_hour=100.0
    )

def test_sanitize_hours():
    # Unsorted, duplicates, negative numbers, out of bounds
    raw = [15, 13, 14, 13, -1, 24, 23, "12", "invalid"]
    sanitized = sanitize_hours(raw)
    assert sanitized == [12, 13, 14, 15, 23]

def test_guardrails_no_op_invariants(sample_battery):
    raw = [
        {
            "note_index": 0,
            "applies": True,  # should be forced to False
            "directive_type": "no_op",
            "structured_adjustment": {"hours": [1, 2]},  # should be forced to None
            "explanation": "test"
        }
    ]
    guarded = validate_and_guardrail_directives(raw, num_notes=1, battery=sample_battery)
    assert len(guarded) == 1
    assert guarded[0].directive_type == "no_op"
    assert guarded[0].applies is False
    assert guarded[0].structured_adjustment is None

def test_guardrails_clamps_solar_factor(sample_battery):
    raw = [
        {
            "note_index": 0,
            "applies": True,
            "directive_type": "solar_reduction",
            "structured_adjustment": {"hours": [14, 13], "factor": 1.5},
            "explanation": "over 100%"
        }
    ]
    guarded = validate_and_guardrail_directives(raw, num_notes=1, battery=sample_battery)
    assert guarded[0].applies is True
    assert guarded[0].structured_adjustment["hours"] == [13, 14]
    assert guarded[0].structured_adjustment["factor"] == 1.0

def test_guardrails_clamps_battery_reserve(sample_battery):
    raw = [
        {
            "note_index": 0,
            "applies": True,
            "directive_type": "minimum_battery_reserve",
            "structured_adjustment": {"hours": [18, 19], "minimum_energy_kwh": 9999.0},
            "explanation": "excessive reserve"
        }
    ]
    guarded = validate_and_guardrail_directives(raw, num_notes=1, battery=sample_battery)
    assert guarded[0].structured_adjustment["minimum_energy_kwh"] == sample_battery.capacity_kwh

def test_guardrails_missing_note_fallback(sample_battery):
    # Only note 1 provided when 2 notes exist
    raw = [
        {
            "note_index": 1,
            "applies": True,
            "directive_type": "no_charge_window",
            "structured_adjustment": {"hours": [2, 3]},
            "explanation": "charge outage"
        }
    ]
    guarded = validate_and_guardrail_directives(raw, num_notes=2, battery=sample_battery)
    assert len(guarded) == 2
    assert guarded[0].note_index == 0
    assert guarded[0].directive_type == "no_op"
    assert guarded[0].applies is False
    assert guarded[1].note_index == 1
    assert guarded[1].directive_type == "no_charge_window"
    assert guarded[1].applies is True
