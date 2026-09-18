from typing import List, Optional, Literal, Union, Dict, Any
from pydantic import BaseModel, Field, field_validator, model_validator

# --- Directive Types & Enums ---
DirectiveType = Literal[
    "solar_reduction",
    "minimum_battery_reserve",
    "no_charge_window",
    "no_discharge_window",
    "max_grid_window",
    "no_op"
]

BatteryActionType = Literal["charge", "discharge", "idle"]

# --- Request Models ---
class HourEntry(BaseModel):
    hour: int = Field(..., ge=0, le=23, description="Unique integer from 0 to 23")
    demand_kwh: float = Field(..., ge=0, description="Campus demand in kWh")
    solar_kwh: float = Field(..., ge=0, description="Forecast solar availability in kWh")
    tariff_bdt_per_kwh: float = Field(..., ge=0, description="Grid tariff in BDT per kWh")

class BatteryConfig(BaseModel):
    capacity_kwh: float = Field(..., gt=0, description="Maximum battery capacity in kWh")
    initial_energy_kwh: float = Field(..., ge=0, description="Energy at the start of hour 0")
    minimum_energy_kwh: float = Field(..., ge=0, description="Base minimum reserve level")
    max_charge_kwh_per_hour: float = Field(..., ge=0, description="Max charge rate in kWh/h")
    max_discharge_kwh_per_hour: float = Field(..., ge=0, description="Max discharge rate in kWh/h")

    @model_validator(mode="after")
    def validate_battery_levels(self):
        if self.minimum_energy_kwh > self.capacity_kwh:
            raise ValueError("minimum_energy_kwh cannot exceed capacity_kwh")
        if self.initial_energy_kwh > self.capacity_kwh:
            raise ValueError("initial_energy_kwh cannot exceed capacity_kwh")
        if self.initial_energy_kwh < self.minimum_energy_kwh:
            raise ValueError("initial_energy_kwh cannot be less than minimum_energy_kwh")
        return self

class OptimizeEnergyRequest(BaseModel):
    scenario_id: str = Field(..., description="Unique scenario identifier")
    operator_notes: List[str] = Field(..., min_length=1, max_length=3, description="1 to 3 operator notes")
    hours: List[HourEntry] = Field(..., min_length=24, max_length=24, description="Hourly profile for 24 hours")
    battery: BatteryConfig

    @field_validator("hours")
    @classmethod
    def validate_hours_sequence(cls, v: List[HourEntry]):
        if len(v) != 24:
            raise ValueError("Must supply exactly 24 hour entries")
        seen_hours = set()
        for entry in v:
            if entry.hour in seen_hours:
                raise ValueError(f"Duplicate hour {entry.hour} found in hours list")
            seen_hours.add(entry.hour)
        if seen_hours != set(range(24)):
            raise ValueError("hours entries must cover hours 0 through 23 exactly")
        return sorted(v, key=lambda x: x.hour)

# --- Response Models ---
class DirectiveInterpretation(BaseModel):
    note_index: int = Field(..., ge=0, description="Index of the corresponding operator note")
    applies: bool = Field(..., description="True for active directives; False only for no_op")
    directive_type: DirectiveType = Field(..., description="Directive type")
    structured_adjustment: Optional[Dict[str, Any]] = Field(None, description="Directive parameters or null for no_op")
    explanation: str = Field(..., description="Human-readable explanation of interpretation")

class HourlyPlanEntry(BaseModel):
    hour: int = Field(..., ge=0, le=23)
    grid_kwh: float = Field(..., ge=0, description="Non-negative grid import")
    solar_used_kwh: float = Field(..., ge=0, description="Solar power consumed")
    battery_action: BatteryActionType = Field(..., description="Battery action: charge, discharge, idle")
    battery_kwh: float = Field(..., ge=0, description="Magnitude of battery action; 0 if idle")
    battery_energy_after_kwh: float = Field(..., ge=0, description="Battery energy after this hour")

class OptimizeEnergyResponse(BaseModel):
    scenario_id: str
    directive_interpretation: List[DirectiveInterpretation]
    hourly_plan: List[HourlyPlanEntry]
    total_grid_kwh: float
    total_cost_bdt: float
    peak_grid_kwh: float
    plan_summary: str

class HealthResponse(BaseModel):
    status: str = "ok"
