import logging
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError

from app.schemas import (
    OptimizeEnergyRequest,
    OptimizeEnergyResponse,
    HealthResponse
)
from app.llm_interpreter import interpret_operator_notes
from app.guardrails import validate_and_guardrail_directives
from app.optimizer import solve_energy_schedule
from app.replay_validator import replay_and_validate_plan

# Configure safe logging (never log secrets or keys)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("gridwise.api")

app = FastAPI(
    title="GridWise LLM - Smart Campus Energy Optimization Service",
    description="LLM-assisted campus energy scheduling and linear programming optimization API for BUP CSE Fest 2026",
    version="1.0.0"
)

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Return controlled 400 error for structural/malformed schema issues."""
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={"detail": "Malformed JSON or structurally invalid request", "errors": exc.errors()}
    )

@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    """Controlled 500 error handler that never exposes stack traces or secret keys."""
    logger.error("Internal processing error: %s", str(exc))
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "An internal error occurred during optimization. Please verify scenario parameters."}
    )

@app.get("/")
async def root():
    """Welcome endpoint for human visitors and browser checks."""
    return {
        "service": "GridWise LLM - Smart Campus Energy Optimization Service",
        "event": "BUP CSE Fest 2026 Hackathon",
        "status": "online",
        "endpoints": {
            "health": "GET /health",
            "optimize_energy": "POST /optimize-energy",
            "api_docs": "GET /docs"
        }
    }

@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint required by the judging harness."""
    return HealthResponse(status="ok")

@app.post("/optimize-energy", response_model=OptimizeEnergyResponse)
async def optimize_energy(req: OptimizeEnergyRequest):
    """
    Main challenge endpoint:
    1. Interprets operator notes via LLM / generative model.
    2. Deterministically validates and guardrails structured directives.
    3. Solves optimal 24-hour campus energy schedule via Linear Programming.
    4. Replays and validates final schedule against all physical & directive rules.
    5. Returns exact response schema with recalculated totals.
    """
    # 1. LLM / Language Directive Interpretation
    raw_directives = await interpret_operator_notes(req.operator_notes, req.battery)

    # 2. Deterministic Guardrails
    guarded_directives = validate_and_guardrail_directives(
        raw_directives,
        num_notes=len(req.operator_notes),
        battery=req.battery
    )

    # 3. Mathematical Optimization (LP / HiGHS)
    try:
        hourly_plan = solve_energy_schedule(req.hours, req.battery, guarded_directives)
    except Exception as e:
        logger.error("Optimization failed: %s", str(e))
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Infeasible scenario or directive conflict: {str(e)}"
        )

    # 4. Independent Replay Validation & Metric Recalculation
    try:
        total_grid, total_cost, peak_grid, summary = replay_and_validate_plan(
            hourly_plan,
            req.hours,
            req.battery,
            guarded_directives
        )
    except Exception as e:
        logger.error("Replay validation failed: %s", str(e))
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Replay validation constraint error: {str(e)}"
        )

    # 5. Return strict response schema
    return OptimizeEnergyResponse(
        scenario_id=req.scenario_id,
        directive_interpretation=guarded_directives,
        hourly_plan=hourly_plan,
        total_grid_kwh=total_grid,
        total_cost_bdt=total_cost,
        peak_grid_kwh=peak_grid,
        plan_summary=summary
    )
