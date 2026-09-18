import json
from pathlib import Path
from starlette.testclient import TestClient
from app.main import app

client = TestClient(app)
SAMPLE_FILE = Path(__file__).resolve().parent.parent / "BUP_CSE_FEST_2026_Preli_Public_Sample_Cases.json"

def test_health_endpoint():
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data == {"status": "ok"}

def test_optimize_energy_sample_01():
    with open(SAMPLE_FILE) as f:
        case = json.load(f)["cases"][0]

    resp = client.post("/optimize-energy", json=case["input"])
    assert resp.status_code == 200
    data = resp.json()

    # Check top-level fields
    assert data["scenario_id"] == case["input"]["scenario_id"]
    assert "directive_interpretation" in data
    assert "hourly_plan" in data
    assert "total_grid_kwh" in data
    assert "total_cost_bdt" in data
    assert "peak_grid_kwh" in data
    assert "plan_summary" in data

    # Check length
    assert len(data["hourly_plan"]) == 24
    assert len(data["directive_interpretation"]) == len(case["input"]["operator_notes"])

    # Check cost
    exp_cost = case["expected_output"]["total_cost_bdt"]
    assert abs(data["total_cost_bdt"] - exp_cost) <= 0.01

def test_malformed_request_returns_400():
    # Missing required fields
    resp = client.post("/optimize-energy", json={"invalid": "payload"})
    assert resp.status_code == 400
    assert "detail" in resp.json()

def test_invalid_hour_count_returns_400():
    with open(SAMPLE_FILE) as f:
        case = json.load(f)["cases"][0]
    bad_input = dict(case["input"])
    bad_input["hours"] = bad_input["hours"][:10]  # Only 10 hours instead of 24
    resp = client.post("/optimize-energy", json=bad_input)
    assert resp.status_code == 400
