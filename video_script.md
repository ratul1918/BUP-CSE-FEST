# 3-Minute Architecture & Solution Presentation Script

**Project**: GridWise LLM — Smart Campus Energy Optimization Challenge  
**Event**: BUP CSE Fest 2026 Hackathon (Online Preliminary Round)  
**Target Duration**: 2 minutes 50 seconds (<= 3:00 max)  
**Solution Video Link**: https://docs.google.com/videos/d/1p8xSfNg9vnMp0SzAO1RG8bSm4z3dci7Z0Lf_UDuorLY/play?usp=sharing  

---

## Slide 1: Title & Problem Context (0:00 - 0:35)
**Visual**: Title slide with project name, system diagram, and campus illustration showing rooftop solar, battery storage, campus demand, and grid connection.

> "Hello judges and reviewers! Today we present **GridWise LLM**, our autonomous campus energy scheduling and optimization service developed for the BUP CSE Fest 2026 Hackathon.
> 
> The challenge is dual-natured: on one side, campus operators issue informal, natural-language operational notes—such as panel cleaning, protection tests, emergency reserves, and feeder constraints, interspersed with administrative distractors. On the other side, the campus needs a mathematically optimal 24-hour dispatch schedule that minimizes grid electricity costs while satisfying physical battery physics, solar availability, and operational directives."

---

## Slide 2: End-to-End Pipeline Architecture (0:35 - 1:20)
**Visual**: Flow diagram highlighting the 4 distinct stages: Unstructured Language $\to$ LLM Interpreter $\to$ Deterministic Guardrails $\to$ 2-Stage Linear Optimizer (HiGHS) $\to$ Replay Validator.

> "To guarantee both high intelligence and mathematical rigor, we built a strict four-stage pipeline:
>
> 1. **LLM Interpretation**: We leverage low-latency generative models via JSON schema prompting to convert notes into structured directives, calculating dynamic battery percentages and mapping whole-hour windows. Unrelated notes are classified as `no_op`.
> 2. **Deterministic Guardrails**: Untrusted model outputs are sanitized against canonical challenge rules before touching any math. We enforce ascending sorted hours, clamp solar reduction factors between 0 and 1, bound reserves within battery capacity, and enforce strict `applies` boolean invariants.
> 3. **Two-Stage Mathematical Optimizer**: Instead of letting an LLM hallucinate schedules, we formulate a Linear Program using the industrial-grade HiGHS solver in SciPy. Stage 1 minimizes 24-hour total grid tariff cost; Stage 2 performs peak grid smoothing to prevent unnecessary battery wear and grid spikes.
> 4. **Independent Replay Validator**: Every output is re-simulated hour-by-hour to verify energy balance, battery state transitions, and end-of-day battery neutrality within 0.01 kWh."

---

## Slide 3: Implementation, Results & Local Verification (1:20 - 2:25)
**Visual**: Screen recording showing terminal running `python verify_public_samples.py` and `pytest`, demonstrating 10/10 sample cases passing with 0.0000 diff. Then showing `curl http://localhost:8000/health` and a sample POST request.

> "Let’s look at our implementation and test results:
> - Built with **FastAPI** for sub-millisecond API response overhead, achieving p95 latency well under 1 second.
> - We tested our system against all 10 canonical public sample cases provided by the organizers.
> - As you can see on the screen, our solver matches the organizer ground-truth directives **100%**, and calculates the exact reference grid electricity cost down to $0.0000$ BDT across all cases.
> - The service exposes `GET /health` and `POST /optimize-energy` with strict Pydantic validation, safe 400 error reporting for malformed schemas, and secure 500 handling without leaking keys or stack traces."

---

## Slide 4: Deployment & Reliability (2:25 - 2:55)
**Visual**: Slide showing Docker containerization, `docker-compose.yml`, multi-provider support (Gemini, OpenAI, Groq), and offline deterministic fallback.

> "For reproducibility and zero-downtime judging:
> - The entire application is containerized with a lightweight, multi-stage Docker image binding to `0.0.0.0:8000`.
> - It includes support for Google Gemini, OpenAI, and Groq, plus a high-precision deterministic NLP parser fallback if external APIs experience network latency or rate limits.
> - The repository includes a clean, copy-paste quickstart in the README that runs locally in seconds.
>
> Thank you for your time and evaluation!"
