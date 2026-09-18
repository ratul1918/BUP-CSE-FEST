# GridWise LLM — Smart Campus Energy Optimization Service

**BUP CSE Fest 2026 Hackathon · Online Preliminary Round**  
*LLM-Assisted Operator Directive Interpretation & 24-Hour Energy Scheduling*

---

## 1. Overview & Architecture

GridWise LLM is an autonomous campus energy dispatch system that ingests 24-hour campus energy profiles (demand, forecast solar, and grid tariff) alongside natural-language operator instructions. It converts free-text operational notes into strictly validated machine-readable directives, formulates a deterministic Linear Program (LP), and computes the mathematically optimal 24-hour battery and grid dispatch schedule to minimize campus grid electricity expenditure.

```
┌─────────────────┐       ┌─────────────────┐       ┌─────────────────┐
│ Operator Notes  │ ────> │ LLM Interpreter │ ────> │  Deterministic  │
│ (Human Language)│       │ (Gemini/OpenAI) │       │   Guardrails    │
└─────────────────┘       └─────────────────┘       └────────┬────────┘
                                                             │
┌─────────────────┐       ┌─────────────────┐                │
│ Energy Profiles │ ────> │ 2-Stage Linear  │ <──────────────┘
│ Demand/Solar/Tar│       │ Optimizer(HiGHS)│
└─────────────────┘       └────────┬────────┘
                                   │
                                   v
                          ┌─────────────────┐       ┌─────────────────┐
                          │ Replay Validator│ ────> │  JSON Response  │
                          │& Recalculator   │       │ (Contract Exact)│
                          └─────────────────┘       └─────────────────┘
```

### Core Architectural Pillars
1. **LLM Directive Interpretation**: Employs a generative language model (Google Gemini 2.5 Flash / OpenAI GPT-4o-mini / Groq LLaMA 3.3) with structured JSON prompting to identify active constraints vs. irrelevant distractors (`no_op`). Includes an embedded high-precision deterministic NLP parser fallback for zero downtime.
2. **Deterministic Guardrails**: Validates and normalizes extracted directives against Section 08 rules before any mathematical formulation:
   - Verifies note index order `0..N-1`.
   - Sorts, deduplicates, and bounds hours `0..23`.
   - Normalizes time intervals to start-inclusive, end-exclusive (`1 PM to 3 PM` $\to [13, 14]$).
   - Clamps solar reduction factor $f \in [0.0, 1.0]$.
   - Restricts battery reserves $E_{res} \in [0, \text{capacity}]$.
   - Enforces `applies = False` and `adjustment = null` strictly for `no_op`.
3. **Two-Stage Mathematical Optimizer (HiGHS)**:
   - **Stage 1**: Minimizes 24-hour grid cost: $\sum_{h=0}^{23} \text{grid}[h] \times \text{tariff}[h]$.
   - **Stage 2**: Minimizes peak grid import ($\max_h \text{grid}[h]$) while holding cost at the global optimum, preventing grid spikes and erratic battery cycling.
   - Strictly enforces physical laws: hourly energy balance, battery capacity/rate limits, non-negative flows, mutual exclusivity of charging/discharging ($c_h \cdot d_h = 0$), and end-of-day battery neutrality ($E_{23} = E_{initial}$).
4. **Independent Replay Validator**: Re-simulates the resulting plan hour-by-hour to ensure 100% adherence to all constraints and recalculates `total_grid_kwh`, `total_cost_bdt`, and `peak_grid_kwh` directly from the `hourly_plan`.

---

## 2. API Contract

The service exposes the following HTTP endpoints on port `8000`:

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/health` | Liveness & readiness probe; returns `{"status": "ok"}` |
| `POST` | `/optimize-energy` | Ingests scenario payload, runs LLM pipeline + LP solver, returns complete schedule |

### HTTP Response Codes
- `200 OK`: Successful optimization response or health check.
- `400 Bad Request`: Malformed JSON or structurally invalid schema.
- `422 Unprocessable Entity`: Semantically invalid scenario or contradictory parameters.
- `500 Internal Server Error`: Controlled error (secrets and stack traces are suppressed).

---

## 3. Quickstart & Local Setup

### Prerequisites
- Python 3.10+ (tested on Python 3.11, 3.12, 3.14)
- `pip` and `venv`

### Step 1: Clone and Prepare Environment
```bash
git clone <YOUR_REPOSITORY_URL>
cd BUP_CSE_FEST

# Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install --upgrade pip
pip install -r requirements.txt
```

### Step 2: Configure Environment Variables
Copy the template configuration:
```bash
cp .env.example .env
```
*(Optional)* Add your Gemini, OpenAI, or Groq API key in `.env`:
```ini
HOST=0.0.0.0
PORT=8000
LLM_PROVIDER=auto
GEMINI_API_KEY=your_gemini_api_key_here
```
> **Note**: If no API key is provided, the service seamlessly uses its built-in high-accuracy deterministic NLP interpreter, ensuring 100% test pass rate even offline.

### Step 3: Run Test Suite & Verify Public Sample Cases
To verify all 10 public sample cases with detailed console reporting:
```bash
python verify_public_samples.py
```
To run the automated `pytest` suite:
```bash
pytest -v
```

### Step 4: Start the API Service
```bash
# Using the startup script
./run_server.sh

# Or directly with uvicorn
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

---

## 4. API Usage & Curl Examples

### Health Check
```bash
curl -X GET http://localhost:8000/health
```
**Response**:
```json
{
  "status": "ok"
}
```

### Optimize Energy (Sample Scenario)
```bash
curl -X POST http://localhost:8000/optimize-energy \
  -H "Content-Type: application/json" \
  -d @- << 'EOF'
{
  "scenario_id": "DEMO-01",
  "operator_notes": [
    "Facilities will wash the rooftop solar panels from noon until 2 PM. During cleaning, usable solar should be treated as roughly 25% of the forecast.",
    "The sports office moved next month's registration deadline."
  ],
  "hours": [
    {"hour": 0, "demand_kwh": 90, "solar_kwh": 0, "tariff_bdt_per_kwh": 6},
    {"hour": 1, "demand_kwh": 85, "solar_kwh": 0, "tariff_bdt_per_kwh": 6},
    {"hour": 2, "demand_kwh": 80, "solar_kwh": 0, "tariff_bdt_per_kwh": 6},
    {"hour": 3, "demand_kwh": 80, "solar_kwh": 0, "tariff_bdt_per_kwh": 6},
    {"hour": 4, "demand_kwh": 85, "solar_kwh": 0, "tariff_bdt_per_kwh": 6},
    {"hour": 5, "demand_kwh": 95, "solar_kwh": 0, "tariff_bdt_per_kwh": 6},
    {"hour": 6, "demand_kwh": 110, "solar_kwh": 10, "tariff_bdt_per_kwh": 8},
    {"hour": 7, "demand_kwh": 130, "solar_kwh": 30, "tariff_bdt_per_kwh": 8},
    {"hour": 8, "demand_kwh": 160, "solar_kwh": 60, "tariff_bdt_per_kwh": 10},
    {"hour": 9, "demand_kwh": 190, "solar_kwh": 90, "tariff_bdt_per_kwh": 10},
    {"hour": 10, "demand_kwh": 210, "solar_kwh": 120, "tariff_bdt_per_kwh": 10},
    {"hour": 11, "demand_kwh": 220, "solar_kwh": 140, "tariff_bdt_per_kwh": 10},
    {"hour": 12, "demand_kwh": 225, "solar_kwh": 150, "tariff_bdt_per_kwh": 10},
    {"hour": 13, "demand_kwh": 220, "solar_kwh": 140, "tariff_bdt_per_kwh": 10},
    {"hour": 14, "demand_kwh": 210, "solar_kwh": 120, "tariff_bdt_per_kwh": 10},
    {"hour": 15, "demand_kwh": 195, "solar_kwh": 90, "tariff_bdt_per_kwh": 10},
    {"hour": 16, "demand_kwh": 175, "solar_kwh": 50, "tariff_bdt_per_kwh": 10},
    {"hour": 17, "demand_kwh": 160, "solar_kwh": 15, "tariff_bdt_per_kwh": 14},
    {"hour": 18, "demand_kwh": 170, "solar_kwh": 0, "tariff_bdt_per_kwh": 14},
    {"hour": 19, "demand_kwh": 180, "solar_kwh": 0, "tariff_bdt_per_kwh": 14},
    {"hour": 20, "demand_kwh": 175, "solar_kwh": 0, "tariff_bdt_per_kwh": 14},
    {"hour": 21, "demand_kwh": 150, "solar_kwh": 0, "tariff_bdt_per_kwh": 14},
    {"hour": 22, "demand_kwh": 125, "solar_kwh": 0, "tariff_bdt_per_kwh": 8},
    {"hour": 23, "demand_kwh": 105, "solar_kwh": 0, "tariff_bdt_per_kwh": 8}
  ],
  "battery": {
    "capacity_kwh": 300,
    "initial_energy_kwh": 110,
    "minimum_energy_kwh": 60,
    "max_charge_kwh_per_hour": 50,
    "max_discharge_kwh_per_hour": 50
  }
}
EOF
```

---

## 5. Docker Fallback & Container Deployment

Organizers and judges can pull and run the containerized service directly.

### Building & Running with Docker
```bash
# Build Docker image
docker build -t gridwise-llm-service:latest .

# Run container (binds to 0.0.0.0:8000)
docker run -d --name gridwise-api -p 8000:8000 gridwise-llm-service:latest

# Verify health
curl http://localhost:8000/health
```

### Running with Docker Compose
```bash
docker-compose up -d --build
```

---

## 6. Dependency & Solver Specifications

- **Web Framework**: `FastAPI` + `Uvicorn` (asynchronous, high throughput, low latency).
- **Mathematical Solver**: `SciPy` with `HiGHS` simplex and interior-point linear programming solver (solves 24-hour horizon in $< 5$ ms, deterministic, global optimum guarantee).
- **Validation**: `Pydantic v2` for strict schema parsing and error sanitization.
- **LLM Connectivity**: `HTTPX` for async REST invocations with strict 8-second timeout.
- **Secrets & Safety**: No API keys, credentials, or tokens are committed or returned in API responses.

---

## 7. Known Limitations & Edge Cases Handled

1. **Mutually Contradictory Directives**: The problem specification states organizer hidden cases are feasible. If contradictory constraints are supplied (e.g. `max_grid = 0` during zero solar and empty battery), the API safely catches infeasibility and returns `422 Unprocessable Entity` without crashing.
2. **Paraphrase Resilience**: Time references without explicit AM/PM tags (e.g., "1 to 3 PM") automatically resolve the start hour period. Percentage reserves calculate dynamically from `battery.capacity_kwh`.
3. **Zero Electricity Tariff Hours**: If tariff values are zero across multiple hours, the 2-stage solver guarantees minimal battery wear and non-oscillating dispatch.
