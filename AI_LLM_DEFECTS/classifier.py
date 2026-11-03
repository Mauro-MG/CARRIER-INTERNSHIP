import json
import time
import requests
from config import PRIMARY_COMPONENTS, SECONDARY_COMPONENTS, FAILURE_REASONS, VALID_SECONDARY_BY_PRIMARY

OLLAMA_URL = "http://localhost:11434/api/chat"


def _extract_json(raw: str) -> dict:
    raw = raw.strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        start = raw.find("{")
        end = raw.rfind("}")
        if start != -1 and end != -1 and end > start:
            return json.loads(raw[start:end + 1])
        raise


def validate_result(result: dict) -> dict:
    result.setdefault("primary_component", "Other")
    result.setdefault("secondary_component", "Other - note issues in comments")
    result.setdefault("failure_reason", "Other")
    result.setdefault("confidence", 0.0)
    result.setdefault("evidence_phrases", [])

    if result["primary_component"] not in PRIMARY_COMPONENTS:
        result["primary_component"] = "Other"

    if result["failure_reason"] not in FAILURE_REASONS:
        result["failure_reason"] = "Other"

    valid_secondaries = VALID_SECONDARY_BY_PRIMARY.get(result["primary_component"], SECONDARY_COMPONENTS)
    if result["secondary_component"] not in valid_secondaries:
        if result["primary_component"] == "Compressor":
            result["secondary_component"] = "Compressor - Mechanical failure"
        elif valid_secondaries:
            result["secondary_component"] = valid_secondaries[0]
        else:
            result["secondary_component"] = "Other - note issues in comments"

    try:
        result["confidence"] = float(result["confidence"])
    except Exception:
        result["confidence"] = 0.0

    result["confidence"] = max(0.0, min(1.0, result["confidence"]))

    if not isinstance(result["evidence_phrases"], list):
        result["evidence_phrases"] = []

    return result


def classify(text: str, historical_context: str = "", model="llama3"):

    prompt = f"""
You are a strict HVAC warranty failure classification engine.

Your job is to classify the MOST RECENT / TARGET claim.

Use older related claims only as supporting context.

RULES:
1. Pick exactly ONE value from each list.
2. Do NOT create new values.
3. Prioritize the MOST RECENT CLAIM.
4. Older claims can support the diagnosis but must not override the latest claim.
5. Identify the root failed component, not just parts replaced.
6. If unsure, use "Other".
7. Return ONLY valid JSON.
8. Confidence should rarely be 1.0. Use:
    0.90-0.95 = very clear evidence
    0.70-0.89 = good evidence
    0.40-0.69 = ambiguous evidence
    0.00-0.39 = weak or uncertain evidence

PRIMARY_COMPONENT OPTIONS:
{PRIMARY_COMPONENTS}

SECONDARY_COMPONENT OPTIONS:
{SECONDARY_COMPONENTS}

FAILURE_REASON OPTIONS:
{FAILURE_REASONS}

TEXT TO CLASSIFY:
{text}

RELATED CLAIM HISTORY:
{historical_context}

RETURN FORMAT:
{{
  "primary_component": "",
  "secondary_component": "",
  "failure_reason": "",
  "confidence": 0.0,
  "evidence_phrases": [],
  "reasoning_summary": ""
}}
"""

    response = requests.post(
        OLLAMA_URL,
        json={
            "model": model,
            "messages": [
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "stream": False,
            "format": "json",
            "options": {
                "temperature": 0,
                "num_predict": 400
            }
        },
        timeout=300
    )



    response.raise_for_status()

    data = response.json()
    raw = data.get("message", {}).get("content", "").strip()

    if not raw:
        return {
            "primary_component": "Other",
            "secondary_component": "Other - note issues in comments",
            "failure_reason": "Other",
            "confidence": 0.0,
            "evidence_phrases": [],
            "reasoning_summary": "Model returned an empty response.",
            "raw_response": raw
        }

    try:
        return json.loads(raw)

    except json.JSONDecodeError:
        print("\nRAW MODEL RESPONSE:")
        print(raw)

        return {
            "primary_component": "Other",
            "secondary_component": "Other - note issues in comments",
            "failure_reason": "Other",
            "confidence": 0.0,
            "evidence_phrases": [],
            "reasoning_summary": "JSON parsing failed. Raw response was not valid JSON.",
            "raw_response": raw
        }