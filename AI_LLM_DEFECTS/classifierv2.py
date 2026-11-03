import json
import requests
from configGEMA import PRIMARY_COMPONENTS, SECONDARY_COMPONENTS, FAILURE_REASONS, VALID_SECONDARY_BY_PRIMARY, HVAC_REASONING_GUIDE
OLLAMA_URL = "http://localhost:11434/api/generate"


def _extract_json(raw: str) -> dict:
    raw = raw.strip()

    # Remove markdown code fences like ```json ... ```
    if raw.startswith("```"):
        raw = raw.replace("```json", "").replace("```JSON", "").replace("```", "").strip()

    if "</think>" in raw:
        raw = raw.split("</think>")[-1].strip()

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

def force_taxonomy_match(value, taxonomy):

    if not value:
        return "Other"

    cleaned = (
        str(value)
        .strip()
        .lower()
        .replace("/", "")
        .replace("-", "")
        .replace("_", "")
        .replace(" ", "")
    )

    for item in taxonomy:

        normalized_item = (
            item.strip()
            .lower()
            .replace("/", "")
            .replace("-", "")
            .replace("_", "")
            .replace(" ", "")
        )

        # Exact normalized match
        if cleaned == normalized_item:
            return item

        # Partial semantic match
        if cleaned in normalized_item:
            return item

        if normalized_item in cleaned:
            return item

    return value

def call_ollama(prompt: str, model: str):
    response = requests.post(
        OLLAMA_URL,
        json={
            "model": model,
            "prompt": prompt,
            "stream": False,
            "keep_alive": "10m",
            "options": {
                "temperature": 0,
                "top_p": 0.1,
                "num_predict": 5000
            }
        },
        timeout=600
    )

    response.raise_for_status()
    data = response.json()

    raw = data.get("response", "").strip()

    if not raw:
        print("\nEMPTY RESPONSE DEBUG")
        print("MODEL:", model)
        print("DONE:", data.get("done"))
        print("DONE_REASON:", data.get("done_reason"))
        print("FULL RESPONSE:", data)

    return raw

def repair_json_response(raw_response: str, model="llama3") -> dict:
    repair_prompt = f"""
Convert the following model response into valid JSON.

Do NOT reclassify.
Do NOT change the meaning.
Only extract the classification labels already present.

Allowed keys:
- primary_component
- secondary_component
- failure_reason

Return ONLY valid JSON.

MODEL RESPONSE:
{raw_response}

JSON FORMAT:
{{
  "primary_component": "",
  "secondary_component": "",
  "failure_reason": ""
}}
"""

    raw, thinking = call_ollama(repair_prompt, model)

    result = _extract_json(raw)

    result["primary_component"] = force_taxonomy_match(
        result.get("primary_component", ""),
        PRIMARY_COMPONENTS
    )

    result["secondary_component"] = force_taxonomy_match(
        result.get("secondary_component", ""),
        SECONDARY_COMPONENTS
    )

    result["failure_reason"] = force_taxonomy_match(
        result.get("failure_reason", ""),
        FAILURE_REASONS
    )

    result = validate_result(result)
    result["model_used"] = f"repair_{model}"

    return result

def classify(text: str, replacement_part_description="", model="gemma3:12b"):

    prompt = f"""
You are an HVAC warranty claim classification engine. Follow the HVAC guide.

{HVAC_REASONING_GUIDE}

IMPORTANT RULES:
1. Use ONLY the categories provided.
2. Return EXACT category names character-for-character from the provided lists.
3. Use only information explicitly stated in the service performed. Reasonable technical inference is allowed when directly supported by the text.
4. If Primary Component cannot be identified, return Ambiguous for all three fields.
5. If Primary Component can be identified, Secondary Component and Failure Reason must NOT be Ambiguous.

PRIMARY COMPONENT OPTIONS:
{PRIMARY_COMPONENTS}

SECONDARY COMPONENT OPTIONS:
{SECONDARY_COMPONENTS}

FAILURE REASON OPTIONS:
{FAILURE_REASONS}

SERVICE PERFORMED:
{text}

REPLACEMENT PART DESCRIPTION:
{replacement_part_description}

OUTPUT REQUIREMENT:
Return one JSON object only.

The response must be parseable by Python json.loads().

Do not return:
- markdown
- bullets
- explanations
- reasoning
- comments
- code fences
- labels outside JSON

Valid response example:
{{
  "primary_component": "Input Devices",
  "secondary_component": "Input devices - Sensor",
  "failure_reason": "Part Failure"
}}

Now return only this JSON object:
{{
  "primary_component": "",
  "secondary_component": "",
  "failure_reason": ""
}}
"""


    raw = call_ollama(prompt, model)

    used_model = model

    if not raw:
        print(f"Empty response from {model}. Retrying with llama3...")

        raw = call_ollama(prompt, "llama3")
        used_model = "llama3"


    try:
        result = _extract_json(raw)

        result["primary_component"] = force_taxonomy_match(
            result.get("primary_component", ""),
            PRIMARY_COMPONENTS
        )

        result["secondary_component"] = force_taxonomy_match(
            result.get("secondary_component", ""),
            SECONDARY_COMPONENTS
        )

        result["failure_reason"] = force_taxonomy_match(
            result.get("failure_reason", ""),
            FAILURE_REASONS
        )

        result = validate_result(result)

        result["model_used"] = used_model

        return result

    except Exception as e:
        print("\nEXCEPTION:")
        print(type(e).__name__)
        print(str(e))

        print("\nRAW MODEL RESPONSE:")
        print(raw)

        try:
            print("Trying JSON repair...")
            result = repair_json_response(raw, model="llama3")
            result["raw_response"] = raw
            return result

        except Exception as repair_error:
            print("JSON repair failed:", repair_error)

            return {
                "primary_component": "Other",
                "secondary_component": "Other - note issues in comments",
                "failure_reason": "Other",
                "confidence": 0.0,
                "evidence_phrases": [],
                "reasoning_summary": "JSON parsing and repair failed.",
                "raw_response": raw,
                "model_used": used_model
            }