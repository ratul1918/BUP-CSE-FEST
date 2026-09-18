import re
import json
import logging
from typing import List, Dict, Any, Optional
import httpx

from app.config import settings
from app.schemas import BatteryConfig

logger = logging.getLogger("gridwise.llm")

SYSTEM_PROMPT = """You are an expert energy scheduling assistant for BUP CSE Fest 2026 Hackathon (GridWise LLM challenge).
Your task is to analyze campus operator natural-language notes and convert each note into a structured JSON directive for a 24-hour optimization horizon (hours 0 to 23).

### OPERATOR NOTE REQUIREMENTS:
Each note must produce exactly one directive interpretation entry matching its note_index (0, 1, ... N-1).
Supported directive types:
1. "solar_reduction": Usable rooftop solar is reduced.
   structured_adjustment: {"hours": [int...], "factor": number}
   NOTE: 'factor' is the fraction of solar REMAINING (0.0 to 1.0).
   Example: "80% reduction" -> factor = 0.2
   Example: "25% of forecast" -> factor = 0.25
   Example: "leave about half" -> factor = 0.5
2. "minimum_battery_reserve": Battery energy must remain at or above a required level in kWh.
   structured_adjustment: {"hours": [int...], "minimum_energy_kwh": number}
   NOTE: If given as percentage of battery capacity, calculate: (percentage / 100.0) * battery_capacity_kwh.
3. "no_charge_window": Battery charging is prohibited/unavailable during specific hours.
   structured_adjustment: {"hours": [int...]}
4. "no_discharge_window": Battery discharging is prohibited/unavailable during specific hours.
   structured_adjustment: {"hours": [int...]}
5. "max_grid_window": Grid import must not exceed a stated kWh in specific hours.
   structured_adjustment: {"hours": [int...], "max_grid_kwh": number}
6. "no_op": Note is unrelated or does not affect the 24-hour schedule (e.g. cafeteria, library, club notices, seminar booking).
   applies: false, structured_adjustment: null

### TIME CONVENTIONS:
- Hours are whole numbers from 0 to 23.
- Time windows are START-INCLUSIVE and END-EXCLUSIVE:
  - "noon until 2 PM" -> [12, 13]
  - "1 PM to 3 PM" or "between 13:00 and 15:00" -> [13, 14]
  - "from 6 PM until 9 PM" -> [18, 19, 20]
  - "from 2 AM until 5 AM" -> [2, 3, 4]
  - "from 11 AM until 1 PM" -> [11, 12]
  - "7 PM until 10 PM" -> [19, 20, 21]

### OUTPUT FORMAT:
Return ONLY a valid JSON array of objects with keys:
[
  {
    "note_index": int,
    "applies": bool,
    "directive_type": str,
    "structured_adjustment": dict or null,
    "explanation": str
  }
]
"""

# -------------------------------------------------------------
# LLM Remote Call Handlers
# -------------------------------------------------------------

async def call_gemini_api(prompt: str, api_key: str, model_name: str) -> Optional[List[Dict[str, Any]]]:
    """Call Google Gemini API using REST endpoint."""
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"
    payload = {
        "contents": [{"parts": [{"text": f"{SYSTEM_PROMPT}\n\n{prompt}"}]}],
        "generationConfig": {
            "temperature": 0.0,
            "responseMimeType": "application/json"
        }
    }
    async with httpx.AsyncClient(timeout=settings.LLM_TIMEOUT_SECONDS) as client:
        resp = await client.post(url, json=payload)
        if resp.status_code == 200:
            data = resp.json()
            candidates = data.get("candidates", [])
            if candidates:
                text = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "")
                return parse_json_array(text)
    return None

async def call_openai_compatible_api(
    base_url: str,
    api_key: str,
    model_name: str,
    prompt: str
) -> Optional[List[Dict[str, Any]]]:
    """Call OpenAI or Groq compatible chat completion endpoint."""
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": model_name,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.0,
        "response_format": {"type": "json_object"}
    }
    async with httpx.AsyncClient(timeout=settings.LLM_TIMEOUT_SECONDS) as client:
        resp = await client.post(base_url, headers=headers, json=payload)
        if resp.status_code == 200:
            data = resp.json()
            text = data["choices"][0]["message"]["content"]
            return parse_json_array(text)
    return None

def parse_json_array(raw_text: str) -> Optional[List[Dict[str, Any]]]:
    """Extract and parse JSON array from model output text."""
    try:
        data = json.loads(raw_text)
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            for k in ["directives", "directive_interpretation", "results", "output"]:
                if k in data and isinstance(data[k], list):
                    return data[k]
    except Exception:
        pass
    
    # Try finding [...] with regex
    match = re.search(r"\[\s*\{.*\}\s*\]", raw_text, re.DOTALL)
    if match:
        try:
            arr = json.loads(match.group(0))
            if isinstance(arr, list):
                return arr
        except Exception:
            pass
    return None


# -------------------------------------------------------------
# High-Accuracy Deterministic NLP Fallback Interpreter
# -------------------------------------------------------------

def parse_hour_token(token: str) -> Optional[int]:
    """Parse hour expressions such as 'noon', 'midnight', '1 PM', '13:00', '2AM'."""
    token = token.strip().lower()
    if token in ["noon", "12 noon", "12:00"]:
        return 12
    if token in ["midnight", "12 midnight", "0:00", "00:00"]:
        return 0
    m_24 = re.match(r"^(\d{1,2}):00$", token)
    if m_24:
        h = int(m_24.group(1))
        if 0 <= h <= 24:
            return h
    m_ampm = re.match(r"^(\d{1,2})(?::00)?\s*(am|pm)$", token)
    if m_ampm:
        val = int(m_ampm.group(1))
        period = m_ampm.group(2)
        if period == "pm":
            return 12 if val == 12 else val + 12
        else:
            return 0 if val == 12 else val
    try:
        val = int(token)
        if 0 <= val <= 24:
            return val
    except ValueError:
        pass
    return None

def extract_time_window(text: str) -> List[int]:
    """Extract whole-hour start-inclusive, end-exclusive window from text."""
    # Pattern: from/between ... until/to/and ...
    patterns = [
        r"(?:from|between)\s+([0-9]{1,2}(?::00)?(?:\s*[ap]m)?|noon|midnight)\s+(?:until|to|and)\s+([0-9]{1,2}(?::00)?(?:\s*[ap]m)?|noon|midnight)",
        r"([0-9]{1,2}(?::00)?(?:\s*[ap]m)?|noon|midnight)\s+(?:until|to|-)\s+([0-9]{1,2}(?::00)?(?:\s*[ap]m)?|noon|midnight)\s*(?:window|maintenance)?"
    ]
    for p in patterns:
        m = re.search(p, text, re.IGNORECASE)
        if m:
            start_str = m.group(1)
            end_str = m.group(2)
            
            # Infer PM for start if start has no am/pm but end has pm
            if "pm" in end_str.lower() and not re.search(r"[ap]m", start_str, re.IGNORECASE) and start_str not in ["noon", "midnight"]:
                h_val = int(re.match(r"\d+", start_str).group(0))
                if h_val < 12 and h_val >= 1:
                    # e.g., "1 to 3 PM" -> 1 PM to 3 PM
                    start_str = f"{h_val} PM"
            if "am" in end_str.lower() and not re.search(r"[ap]m", start_str, re.IGNORECASE) and start_str not in ["noon", "midnight"]:
                h_val = int(re.match(r"\d+", start_str).group(0))
                if h_val < 12:
                    start_str = f"{h_val} AM"

            start_h = parse_hour_token(start_str)
            end_h = parse_hour_token(end_str)
            if start_h is not None and end_h is not None and start_h < end_h:
                return list(range(start_h, end_h))

    return []

def heuristic_interpret_note(
    note: str,
    note_index: int,
    battery: BatteryConfig
) -> Dict[str, Any]:
    """
    Robust rule-based interpreter for operator notes.
    Handles solar reductions, battery reserves (% and kWh), charging/discharging outages,
    grid limits, and distractor detection.
    """
    text = note.strip()
    lowered = text.lower()

    # 1. Distractor detection
    distractor_keywords = [
        "cafeteria", "sports office", "library", "registration deadline",
        "book-return", "club notices", "student affairs", "seminar room",
        "holiday", "bus schedule", "parking"
    ]
    if any(k in lowered for k in distractor_keywords) and not any(k in lowered for k in ["battery", "solar", "grid", "feeder", "transformer"]):
        return {
            "note_index": note_index,
            "applies": False,
            "directive_type": "no_op",
            "structured_adjustment": None,
            "explanation": "This note refers to unrelated campus administrative events."
        }

    hours = extract_time_window(text)

    # 2. Solar Reduction
    if any(w in lowered for w in ["solar", "rooftop solar", "pv", "panel", "sunlight", "cleaning"]):
        # Check reduction fraction/factor
        factor = 1.0
        # "roughly 25% of the forecast" or "about 20%"
        m_pct = re.search(r"(\d+)\s*%\s*(?:of\s+(?:the\s+)?forecast|of\s+normal)", lowered)
        if m_pct:
            factor = float(m_pct.group(1)) / 100.0
        elif "half" in lowered or "50%" in lowered:
            if "reduction" in lowered or "cut" in lowered:
                factor = 0.5
            else:
                factor = 0.5
        elif "one-fifth" in lowered:
            factor = 0.2
        elif "one-fourth" in lowered:
            factor = 0.25
        else:
            m_red = re.search(r"(\d+)\s*%\s*reduction", lowered)
            if m_red:
                reduction_pct = float(m_red.group(1))
                factor = (100.0 - reduction_pct) / 100.0
            else:
                m_drop = re.search(r"drop\s+to\s+(?:about\s+)?(\d+)\s*%", lowered)
                if m_drop:
                    factor = float(m_drop.group(1)) / 100.0

        return {
            "note_index": note_index,
            "applies": True,
            "directive_type": "solar_reduction",
            "structured_adjustment": {"hours": hours, "factor": factor},
            "explanation": f"Solar output is reduced to factor {factor} during specified window."
        }

    # 3. Minimum Battery Reserve
    if any(w in lowered for w in ["reserve", "remain in the battery", "stored in the battery", "in the battery", "keep at least"]):
        # Check percentage of capacity: e.g. "50% of the battery capacity"
        m_pct = re.search(r"(\d+)\s*%\s*(?:of\s+(?:the\s+)?battery\s+capacity)?", lowered)
        m_kwh = re.search(r"(\d+(?:\.\d+)?)\s*kwh", lowered)
        
        reserve_kwh = battery.minimum_energy_kwh
        if "%" in lowered and m_pct:
            pct_val = float(m_pct.group(1))
            reserve_kwh = (pct_val / 100.0) * battery.capacity_kwh
        elif m_kwh:
            reserve_kwh = float(m_kwh.group(1))

        return {
            "note_index": note_index,
            "applies": True,
            "directive_type": "minimum_battery_reserve",
            "structured_adjustment": {"hours": hours, "minimum_energy_kwh": reserve_kwh},
            "explanation": f"Maintain minimum battery reserve of {reserve_kwh} kWh during window."
        }

    # 4. No Discharge Window
    if any(w in lowered for w in ["not discharge", "no-discharge", "disable discharge", "discharging is disabled", "discharging is unavailable"]):
        return {
            "note_index": note_index,
            "applies": True,
            "directive_type": "no_discharge_window",
            "structured_adjustment": {"hours": hours},
            "explanation": "Battery discharging is restricted during window."
        }

    # 5. No Charge Window
    if any(w in lowered for w in ["not charge", "no-charge", "charger will be isolated", "charging circuit will be unavailable", "charging is disabled", "do not charge"]):
        return {
            "note_index": note_index,
            "applies": True,
            "directive_type": "no_charge_window",
            "structured_adjustment": {"hours": hours},
            "explanation": "Battery charging is disabled during window."
        }

    # 6. Max Grid Window
    if any(w in lowered for w in ["grid import", "grid intake", "feeder", "transformer limit", "substation"]):
        m_kwh = re.search(r"(\d+(?:\.\d+)?)\s*kwh", lowered)
        cap_val = float(m_kwh.group(1)) if m_kwh else 0.0
        return {
            "note_index": note_index,
            "applies": True,
            "directive_type": "max_grid_window",
            "structured_adjustment": {"hours": hours, "max_grid_kwh": cap_val},
            "explanation": f"Grid import is capped at {cap_val} kWh during window."
        }

    # Default fallback: no_op
    return {
        "note_index": note_index,
        "applies": False,
        "directive_type": "no_op",
        "structured_adjustment": None,
        "explanation": "Note does not alter the energy schedule."
    }


# -------------------------------------------------------------
# Main Interpreter Entrypoint
# -------------------------------------------------------------

async def interpret_operator_notes(
    notes: List[str],
    battery: BatteryConfig
) -> List[Dict[str, Any]]:
    """
    Interprets operator notes into structured directives.
    Invokes configured LLM provider when keys are available;
    seamlessly falls back to high-accuracy deterministic parser if unconfigured or on failure.
    """
    user_prompt = f"Battery Capacity: {battery.capacity_kwh} kWh\nOperator Notes:\n"
    for i, note in enumerate(notes):
        user_prompt += f"[{i}] {note}\n"

    parsed_result = None

    # Determine provider
    provider = settings.LLM_PROVIDER
    if provider == "auto":
        if settings.GEMINI_API_KEY:
            provider = "gemini"
        elif settings.OPENAI_API_KEY:
            provider = "openai"
        elif settings.GROQ_API_KEY:
            provider = "groq"
        else:
            provider = "heuristic"

    # Attempt LLM call
    if provider == "gemini" and settings.GEMINI_API_KEY:
        try:
            logger.info("Interpreting notes with Gemini API (%s)", settings.GEMINI_MODEL)
            parsed_result = await call_gemini_api(user_prompt, settings.GEMINI_API_KEY, settings.GEMINI_MODEL)
        except Exception as e:
            logger.warning("Gemini call failed: %s, falling back to heuristic parser", e)

    elif provider == "openai" and settings.OPENAI_API_KEY:
        try:
            logger.info("Interpreting notes with OpenAI API (%s)", settings.OPENAI_MODEL)
            parsed_result = await call_openai_compatible_api(
                "https://api.openai.com/v1/chat/completions",
                settings.OPENAI_API_KEY,
                settings.OPENAI_MODEL,
                user_prompt
            )
        except Exception as e:
            logger.warning("OpenAI call failed: %s, falling back to heuristic parser", e)

    elif provider == "groq" and settings.GROQ_API_KEY:
        try:
            logger.info("Interpreting notes with Groq API (%s)", settings.GROQ_MODEL)
            parsed_result = await call_openai_compatible_api(
                "https://api.groq.com/openai/v1/chat/completions",
                settings.GROQ_API_KEY,
                settings.GROQ_MODEL,
                user_prompt
            )
        except Exception as e:
            logger.warning("Groq call failed: %s, falling back to heuristic parser", e)

    # If LLM returned valid list, verify coverage
    if isinstance(parsed_result, list) and len(parsed_result) == len(notes):
        return parsed_result

    # Fallback to deterministic NLP heuristic interpreter
    logger.info("Using deterministic NLP interpreter for %d notes", len(notes))
    fallback_result = []
    for i, note in enumerate(notes):
        fallback_result.append(heuristic_interpret_note(note, i, battery))

    return fallback_result
