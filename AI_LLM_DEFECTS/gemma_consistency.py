import time
import pandas as pd
import json
import subprocess
import ollama 
from best_gema_config import (
    PRIMARY_COMPONENTS,
    SECONDARY_COMPONENTS,
    FAILURE_REASONS,
    map_secondary_group,
    normalize_secondary,
    SECONDARY_GROUP_MAPPING,
    VALID_SECONDARY_BY_PRIMARY,
    HVAC_REASONING_GUIDE
)

INPUT_XLSX = "qwen_vs_gemma_real_field_accuracy.xlsx"
INPUT_SHEET = "AllRowsMerged"

OUTPUT_XLSX = "gemma_consistency_results.xlsx"

MODEL = "gemma4:12B"

SERVICE_COL = "service_text"
PART_COL = "ReplacementPartDescription"

ACTUAL_PRIMARY_COL = "actual_primary"
ACTUAL_SECONDARY_COL = "actual_secondary"
ACTUAL_FAILURE_COL = "actual_failure"

OLD_GEMMA_PRIMARY_COL = "pred_primary_gemma"
OLD_GEMMA_SECONDARY_COL = "pred_secondary_gemma"
OLD_GEMMA_FAILURE_COL = "pred_failure_gemma"

NEW_GEMMA_PRIMARY_COL = "pred_primary_gemma_rerun"
NEW_GEMMA_SECONDARY_COL = "pred_secondary_gemma_rerun"
NEW_GEMMA_FAILURE_COL = "pred_failure_gemma_rerun"

NEW_GEMMA_MODEL_COL = "gemma_rerun_model_  used"
NEW_GEMMA_CONFIDENCE_COL = "gemma_rerun_confidence"

# Set to None to run all rows
MAX_ROWS = None

# Saves progress every N rows
SAVE_EVERY = 25


def clean_text(value):
    if pd.isna(value):
        return ""
    return str(value).strip()


def normalize_key(value):
    return (
        str(value)
        .strip()
        .upper()
        .replace(" ", "")
        .replace("_", "")
        .replace("-", "")
        .replace("/", "")
    )


def force_match(value, taxonomy_list):
    cleaned = normalize_key(value)

    for item in taxonomy_list:
        if cleaned == normalize_key(item):
            return item

    return value


def normalize_to_taxonomy(value, taxonomy_list):
    if pd.isna(value):
        return ""

    if taxonomy_list == SECONDARY_COMPONENTS:
        grouped = map_secondary_group(normalize_secondary(value))
        return force_match(grouped, SECONDARY_COMPONENTS)

    return force_match(value, taxonomy_list)


def to_bool(value):
    if isinstance(value, bool):
        return value

    text = str(value).strip().upper()

    return text in {"TRUE", "1", "YES", "Y", "CORRECT"}


def pct(value):
    return round(value * 100, 2)


def save_workbook(df, summary_df, output_path):
    changed_any = df[
        (~df["primary_consistent"])
        | (~df["secondary_consistent"])
        | (~df["failure_consistent"])
    ].copy()

    exact_changed = df[~df["exact_prediction_consistent"]].copy()

    old_correct_new_wrong = df[
        (df["old_exact_match_gemma"])
        & (~df["new_exact_match_gemma"])
    ].copy()

    old_wrong_new_correct = df[
        (~df["old_exact_match_gemma"])
        & (df["new_exact_match_gemma"])
    ].copy()

    both_exact_correct = df[
        (df["old_exact_match_gemma"])
        & (df["new_exact_match_gemma"])
    ].copy()

    both_exact_wrong = df[
        (~df["old_exact_match_gemma"])
        & (~df["new_exact_match_gemma"])
    ].copy()

    with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
        summary_df.to_excel(writer, sheet_name="Summary", index=False)
        df.to_excel(writer, sheet_name="AllRowsConsistency", index=False)
        changed_any.to_excel(writer, sheet_name="ChangedAnyField", index=False)
        exact_changed.to_excel(writer, sheet_name="ChangedExactPrediction", index=False)
        old_correct_new_wrong.to_excel(writer, sheet_name="OldCorrectNewWrong", index=False)
        old_wrong_new_correct.to_excel(writer, sheet_name="OldWrongNewCorrect", index=False)
        both_exact_correct.to_excel(writer, sheet_name="BothExactCorrect", index=False)
        both_exact_wrong.to_excel(writer, sheet_name="BothExactWrong", index=False)


def build_summary(df):
    summary_rows = [
        {
            "Metric": "Total rows",
            "Value": len(df),
        },

        {
            "Metric": "Primary Consistency %",
            "Value": pct(df["primary_consistent"].mean()),
        },
        {
            "Metric": "Secondary Consistency %",
            "Value": pct(df["secondary_consistent"].mean()),
        },
        {
            "Metric": "Failure Reason Consistency %",
            "Value": pct(df["failure_consistent"].mean()),
        },
        {
            "Metric": "Exact Prediction Consistency %",
            "Value": pct(df["exact_prediction_consistent"].mean()),
        },
    ]

    return pd.DataFrame(summary_rows)


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

def normalize_grouped_secondary(value):
    matched = force_taxonomy_match(value, SECONDARY_COMPONENTS)
    return SECONDARY_GROUP_MAPPING(matched)


def validate_result(result: dict) -> dict:
    result.setdefault("primary_component", "Other")
    result.setdefault("secondary_component", "Other - note issues in comments")
    result.setdefault("failure_reason", "Other")
    result.setdefault("confidence", 0.0)

    if result["primary_component"] not in PRIMARY_COMPONENTS:
        result["primary_component"] = "Other"

    if result["failure_reason"] not in FAILURE_REASONS:
        result["failure_reason"] = "Other"

    valid_secondaries = VALID_SECONDARY_BY_PRIMARY.get(result["primary_component"], SECONDARY_COMPONENTS)
    if result["secondary_component"] not in valid_secondaries:
        if result["primary_component"] == "Compressor":
            result["secondary_component"] = "Compressor-Mechanical failure"
        elif valid_secondaries:
            result["secondary_component"] = valid_secondaries[0]
        else:
            result["secondary_component"] = "Other - note issues in comments"

    try:
        result["confidence"] = float(result["confidence"])
    except Exception:
        result["confidence"] = 0.0

    result["confidence"] = max(0.0, min(1.0, result["confidence"]))

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

def unload_model(model: str):
    try:
        subprocess.run(
            ["ollama", "stop", model],
            capture_output=True,
            text=True,
            timeout=30
        )
        time.sleep(2)
    except Exception as e:
        print(f"Could not unload model {model}: {e}")

def postprocess_prediction(pred, service_text):
    cleaned = {
        "primary_component": pred.get("primary_component", "Other"),
        "secondary_component": pred.get("secondary_component", "Nc-Other"),
        "failure_reason": pred.get("failure_reason", "Other"),
    }

    needs_review = False
    text = str(service_text).lower()

    # Normalize secondary to grouped taxonomy
    cleaned["secondary_component"] = map_secondary_group(
        cleaned["secondary_component"]
    )

    # -------------------------
    # High-confidence wiring
    # -------------------------
    if any(k in text for k in [
        "loose connection", "bad connection", "reconnected", "rewired",
        "wire harness", "wires pulled loose", "wrong terminal",
        "wrong terminals", "miswired", "crossed wiring", "pinched wire",
        "damaged wiring", "loose wiring"
    ]):
        cleaned["primary_component"] = "Electrical controls"
        cleaned["secondary_component"] = "Electrical Controls-Wiring"
        needs_review = True

    # -------------------------
    # High-confidence input devices
    # -------------------------
    if any(k in text for k in [
        "transducer", "thermistor", "temp sensor", "temperature sensor",
        "pressure transducer", "static pressure transducer",
        "bad thermistor", "sensor inoperable"
    ]):
        if not any(k in text for k in [
            "loose connection", "bad connection", "rewired",
            "wire harness", "reconnected", "pinched wire"
        ]):
            cleaned["primary_component"] = "Input Devices"
            cleaned["secondary_component"] = "Input Devices-Sensor"
            needs_review = True

    # -------------------------
    # Leak handling
    # -------------------------
    if any(k in text for k in ["leak", "leaking", "leaked"]):
        cleaned["primary_component"] = "Non-component"
        cleaned["secondary_component"] = "Nc-Leak"
        needs_review = True

    # -------------------------
    # Reset / no fault found
    # -------------------------
    if any(k in text for k in [
        "reset alarm", "reset alarms", "ran fine", "would not trip",
        "unable to duplicate", "no problem found", "no fault found",
        "operating normally"
    ]) and not any(k in text for k in [
        "replaced", "installed", "ordered", "bad connection", "rewired"
    ]):
        cleaned["primary_component"] = "Non-component"
        cleaned["secondary_component"] = "Nc-No Fault Found"
        cleaned["failure_reason"] = "Resettable alarms"
        needs_review = True

    # -------------------------
    # Manufacturing high-confidence
    # -------------------------
    if any(k in text for k in [
        "from factory", "out of package", "as shipped",
        "factory installed", "factory charged", "shipped with",
        "shipped without"
    ]):
        cleaned["failure_reason"] = "Manufacturing"
        needs_review = True

    # -------------------------
    # Network controls
    # -------------------------
    if any(k in text for k in [
        "bacnet", "ccn", "bas", "lon", "communication",
        "not communicating", "controller integration"
    ]):
        cleaned["failure_reason"] = "Network Controls"
        needs_review = True

    # -------------------------
    # Validate final labels
    # -------------------------
    if cleaned["primary_component"] not in PRIMARY_COMPONENTS:
        cleaned["primary_component"] = "Other"
        needs_review = True

    if cleaned["secondary_component"] not in SECONDARY_COMPONENTS:
        cleaned["secondary_component"] = "Nc-Other"
        needs_review = True

    if cleaned["failure_reason"] not in FAILURE_REASONS:
        cleaned["failure_reason"] = "Other"
        needs_review = True
    cleaned = {
    "primary_component": pred.get("primary_component", "Other"),
    "secondary_component": pred.get("secondary_component", "Nc-Other"),
    "failure_reason": pred.get("failure_reason", "Other"),
    "confidence": pred.get("confidence", 0.0),
}
    return cleaned, needs_review

def call_ollama(prompt: str, model: str, force_json: bool = False) -> str:
    """
    Calls Ollama via the official Python library.
    Leverages `format='json'` to structurally enforce valid output constraints.
    """
    try:
        options = {
            "temperature": 0.0,
            "top_p": 0.1,
            "num_ctx": 8192,
            "num_predict": 400
        }

        response = ollama.generate(
            model=model,
            prompt=prompt,
            format="json" if force_json else "",
            options=options
        )
        
        raw = response.get("response", "").strip()

        if not raw:
            print("\nEMPTY RESPONSE DEBUG")
            print("MODEL:", model)
            print("FULL RESPONSE OBJECT:", response)

        return raw

    except Exception as e:
        print(f"Ollama library error while calling {model}: {e}")
        return ""


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

Return ONLY valid JSON matching this schema:
{{
  "failure_reason": "",
  "primary_component": "",
  "secondary_component": ""
}}

MODEL RESPONSE:
{raw_response}
"""

    raw = call_ollama(repair_prompt, model, force_json=False)
    result = _extract_json(raw)

    result["primary_component"] = force_taxonomy_match(
        result.get("primary_component", ""),
        PRIMARY_COMPONENTS
    )

    result["secondary_component"] = normalize_grouped_secondary(
        result.get("secondary_component", "")
    )

    result["failure_reason"] = force_taxonomy_match(
        result.get("failure_reason", ""),
        FAILURE_REASONS
    )

    result = validate_result(result)
    result["model_used"] = f"repair_{model}"


    return result


def classify(text: str, replacement_part_description="", model="gemma4:12b"):
    prompt = f"""
You are an HVAC warranty claim classification engine. Follow the HVAC guide.

{HVAC_REASONING_GUIDE}

IMPORTANT RULES:
1. Use ONLY the categories provided.
2. Return EXACT category names character-for-character from the provided lists.
3. Use only information explicitly stated in the service performed. Reasonable technical inference is allowed when directly supported by the text.
4. If Primary Component cannot be identified, return Ambiguous for all three fields.
5. If Primary Component can be identified, Secondary Component and Failure Reason must NOT be Ambiguous.
6. RELATED PART DESCRIPTION may provide additional context use it only to strengthen or clarify conclusions supported by the current claim.

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

confidence meaning

from 0.0 to 1.0

Confidence should represent how certain you are that the classification is correct.

OUTPUT REQUIREMENT:
Provide the output matching this schema:


{{
  "failure_reason": "",
  "primary_component": "",
  "secondary_component": "",
  "confidence": 0.0
}}
"""

    raw = call_ollama(prompt, model, force_json=True)
    used_model = model

    if not raw:
        print(f"Empty response from {model}. Retrying with llama3...")
        raw = call_ollama(prompt, "llama3", force_json=False)
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
        result, needs_review = postprocess_prediction(result, text)
        result["needs_review"] = needs_review

        return result

    except Exception as e:
        print("\nEXCEPTION:")
        print(type(e).__name__)
        print(str(e))

        print("\nRAW MODEL RESPONSE:")
        print(raw)
        try:
            print(f"Retrying {used_model} after unloading model...")
            unload_model(used_model)

            raw = call_ollama(prompt, used_model, force_json=False)

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
            result["model_used"] = f"{used_model}_retry_after_unload"

            return result

        except Exception as retry_error:
            print("Retry after unload failed:", retry_error)

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

            }




def main():
    overall_start = time.perf_counter()

    df = pd.read_excel(INPUT_XLSX, sheet_name=INPUT_SHEET)
    df.columns = [str(c).strip() for c in df.columns]

    required_cols = [
        SERVICE_COL,
        ACTUAL_PRIMARY_COL,
        ACTUAL_SECONDARY_COL,
        ACTUAL_FAILURE_COL,
        OLD_GEMMA_PRIMARY_COL,
        OLD_GEMMA_SECONDARY_COL,
        OLD_GEMMA_FAILURE_COL,
    ]

    for col in required_cols:
        if col not in df.columns:
            raise ValueError(
                f"Missing required column: {col}\n"
                f"Available columns:\n{df.columns.tolist()}"
            )

    if PART_COL not in df.columns:
        df[PART_COL] = ""

    df = df[
        df[SERVICE_COL].notna()
        & (df[SERVICE_COL].astype(str).str.strip() != "")
    ].copy()

    if MAX_ROWS is not None:
        df = df.head(MAX_ROWS).copy()

    # Normalize actual labels
    df[ACTUAL_PRIMARY_COL] = df[ACTUAL_PRIMARY_COL].apply(
        lambda x: normalize_to_taxonomy(x, PRIMARY_COMPONENTS)
    )
    df[ACTUAL_SECONDARY_COL] = df[ACTUAL_SECONDARY_COL].apply(
        lambda x: normalize_to_taxonomy(x, SECONDARY_COMPONENTS)
    )
    df[ACTUAL_FAILURE_COL] = df[ACTUAL_FAILURE_COL].apply(
        lambda x: normalize_to_taxonomy(x, FAILURE_REASONS)
    )

    # Normalize existing Gemma predictions
    df[OLD_GEMMA_PRIMARY_COL] = df[OLD_GEMMA_PRIMARY_COL].apply(
        lambda x: normalize_to_taxonomy(x, PRIMARY_COMPONENTS)
    )
    df[OLD_GEMMA_SECONDARY_COL] = df[OLD_GEMMA_SECONDARY_COL].apply(
        lambda x: normalize_to_taxonomy(x, SECONDARY_COMPONENTS)
    )
    df[OLD_GEMMA_FAILURE_COL] = df[OLD_GEMMA_FAILURE_COL].apply(
        lambda x: normalize_to_taxonomy(x, FAILURE_REASONS)
    )

    # Create rerun columns if missing
    for col in [
        NEW_GEMMA_PRIMARY_COL,
        NEW_GEMMA_SECONDARY_COL,
        NEW_GEMMA_FAILURE_COL,
        NEW_GEMMA_MODEL_COL,
    ]:
        if col not in df.columns:
            df[col] = ""

    if NEW_GEMMA_CONFIDENCE_COL not in df.columns:
        df[NEW_GEMMA_CONFIDENCE_COL] = 0.0

    print(f"Rows to check for Gemma consistency: {len(df)}")

    for counter, (idx, row) in enumerate(df.iterrows(), start=1):
        existing_primary = clean_text(row.get(NEW_GEMMA_PRIMARY_COL, ""))
        existing_secondary = clean_text(row.get(NEW_GEMMA_SECONDARY_COL, ""))
        existing_failure = clean_text(row.get(NEW_GEMMA_FAILURE_COL, ""))

        # Resume support: skip if already processed
        if existing_primary and existing_secondary and existing_failure:
            print(f"[{counter}/{len(df)}] Skipping already processed row {idx}")
            continue

        print(f"[{counter}/{len(df)}] Rerunning Gemma on row {idx}")

        service_text = clean_text(row[SERVICE_COL])
        replacement_part = clean_text(row.get(PART_COL, "")) or "Not Provided"

        result = classify(
            text=service_text,
            replacement_part_description=replacement_part,
            model=MODEL,
        )

        if (
            not result
            or not result.get("primary_component")
            or not result.get("secondary_component")
            or not result.get("failure_reason")
        ):
            print(f"   ! Empty result at row {idx}. Retrying with llama3.")
            result = classify(
                text=service_text,
                replacement_part_description=replacement_part,
                model="llama3",
            )

        new_primary = normalize_to_taxonomy(
            result.get("primary_component", ""),
            PRIMARY_COMPONENTS,
        )

        new_secondary = normalize_to_taxonomy(
            result.get("secondary_component", ""),
            SECONDARY_COMPONENTS,
        )

        new_failure = normalize_to_taxonomy(
            result.get("failure_reason", ""),
            FAILURE_REASONS,
        )

        df.at[idx, NEW_GEMMA_PRIMARY_COL] = new_primary
        df.at[idx, NEW_GEMMA_SECONDARY_COL] = new_secondary
        df.at[idx, NEW_GEMMA_FAILURE_COL] = new_failure
        df.at[idx, NEW_GEMMA_MODEL_COL] = result.get("model_used", MODEL)
        df.at[idx, NEW_GEMMA_CONFIDENCE_COL] = float(result.get("confidence", 0.0) or 0.0)

        if counter % SAVE_EVERY == 0:
            print(f"   Saving checkpoint at row {counter}...")
            temp_df = df.copy()
            add_metrics(temp_df)
            temp_summary = build_summary(temp_df)
            save_workbook(temp_df, temp_summary, OUTPUT_XLSX)

    add_metrics(df)
    summary_df = build_summary(df)

    print("\n=== GEMMA CONSISTENCY SUMMARY ===")
    print(summary_df.to_string(index=False))



    save_workbook(df, summary_df, OUTPUT_XLSX)

    elapsed = (time.perf_counter() - overall_start) / 60
    print(f"\nTotal runtime: {elapsed:.2f} minutes")
    print(f"Excel created: {OUTPUT_XLSX}")


def add_metrics(df):
    # Consistency: old Gemma prediction vs rerun Gemma prediction
    df["primary_consistent"] = (
        df[OLD_GEMMA_PRIMARY_COL].apply(normalize_key)
        == df[NEW_GEMMA_PRIMARY_COL].apply(normalize_key)
    )

    df["secondary_consistent"] = (
        df[OLD_GEMMA_SECONDARY_COL].apply(normalize_key)
        == df[NEW_GEMMA_SECONDARY_COL].apply(normalize_key)
    )

    df["failure_consistent"] = (
        df[OLD_GEMMA_FAILURE_COL].apply(normalize_key)
        == df[NEW_GEMMA_FAILURE_COL].apply(normalize_key)
    )

    df["exact_prediction_consistent"] = (
        df["primary_consistent"]
        & df["secondary_consistent"]
        & df["failure_consistent"]
    )

    # Old Gemma accuracy vs actual labels
    df["old_primary_match_gemma"] = (
        df[OLD_GEMMA_PRIMARY_COL].apply(normalize_key)
        == df[ACTUAL_PRIMARY_COL].apply(normalize_key)
    )

    df["old_secondary_match_gemma"] = (
        df[OLD_GEMMA_SECONDARY_COL].apply(normalize_key)
        == df[ACTUAL_SECONDARY_COL].apply(normalize_key)
    )

    df["old_failure_match_gemma"] = (
        df[OLD_GEMMA_FAILURE_COL].apply(normalize_key)
        == df[ACTUAL_FAILURE_COL].apply(normalize_key)
    )

    df["old_exact_match_gemma"] = (
        df["old_primary_match_gemma"]
        & df["old_secondary_match_gemma"]
        & df["old_failure_match_gemma"]
    )

    # New Gemma accuracy vs actual labels
    df["new_primary_match_gemma"] = (
        df[NEW_GEMMA_PRIMARY_COL].apply(normalize_key)
        == df[ACTUAL_PRIMARY_COL].apply(normalize_key)
    )

    df["new_secondary_match_gemma"] = (
        df[NEW_GEMMA_SECONDARY_COL].apply(normalize_key)
        == df[ACTUAL_SECONDARY_COL].apply(normalize_key)
    )

    df["new_failure_match_gemma"] = (
        df[NEW_GEMMA_FAILURE_COL].apply(normalize_key)
        == df[ACTUAL_FAILURE_COL].apply(normalize_key)
    )

    df["new_exact_match_gemma"] = (
        df["new_primary_match_gemma"]
        & df["new_secondary_match_gemma"]
        & df["new_failure_match_gemma"]
    )

    # Change type
    df["primary_change_type"] = df.apply(
        lambda r: "SAME" if r["primary_consistent"]
        else f'{r[OLD_GEMMA_PRIMARY_COL]} -> {r[NEW_GEMMA_PRIMARY_COL]}',
        axis=1
    )

    df["secondary_change_type"] = df.apply(
        lambda r: "SAME" if r["secondary_consistent"]
        else f'{r[OLD_GEMMA_SECONDARY_COL]} -> {r[NEW_GEMMA_SECONDARY_COL]}',
        axis=1
    )

    df["failure_change_type"] = df.apply(
        lambda r: "SAME" if r["failure_consistent"]
        else f'{r[OLD_GEMMA_FAILURE_COL]} -> {r[NEW_GEMMA_FAILURE_COL]}',
        axis=1
    )


if __name__ == "__main__":
    main()