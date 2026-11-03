import os
import json
import time
import pandas as pd
from classifier import classify

INPUT_CSV = "data_historical_claims.csv"
OUTPUT_CSV = "llama3_full_historical_predictions_update_ready.csv"
OUTPUT_XLSX = "llama3_full_historical_predictions_update_ready.xlsx"

# Change this to your actual primary key column
PRIMARY_KEY_COL = "ID"

# Change these to your existing classification column names
CURRENT_PRIMARY_COL = "FirstComponentPred"
CURRENT_SECONDARY_COL = "SecondaryComponentPred"
CURRENT_REASON_COL = "FailureReasonPred"

TEXT_COL = "ServicePerformed"

CHECKPOINT_EVERY = 100
SLEEP_BETWEEN_CALLS = 0.2


def safe_text(value):
    if pd.isna(value):
        return ""
    return str(value).strip()


def validate_prediction(result):
    required = [
        "primary_component",
        "secondary_component",
        "failure_reason",
        "confidence",
        "evidence_phrases",
        "reasoning_summary",
    ]

    for key in required:
        if key not in result:
            return False

    return True


def main():
    df = pd.read_csv(INPUT_CSV)

    required_cols = [
        PRIMARY_KEY_COL,
        CURRENT_PRIMARY_COL,
        CURRENT_SECONDARY_COL,
        CURRENT_REASON_COL,
        TEXT_COL,
    ]

    for col in required_cols:
        if col not in df.columns:
            raise ValueError(f"Missing required column: {col}")

    df = df.copy()

    df["FirstComponent_AI"] = ""
    df["SecondaryComponent_AI"] = ""
    df["FailureReason_AI"] = ""
    df["AI_Confidence"] = 0.0
    df["AI_EvidencePhrases"] = ""
    df["AI_ReasoningSummary"] = ""
    df["AI_Status"] = ""
    df["AI_RawResponse"] = ""

    total = len(df)

    print(f"Starting full LLaMA3 classification for {total} rows...")

    for idx, row in df.iterrows():
        record_id = row.get(PRIMARY_KEY_COL, "")
        service_text = safe_text(row.get(TEXT_COL, ""))

        if not service_text:
            df.at[idx, "AI_Status"] = "Skipped - empty ServicePerformed"
            continue

        try:
            print(f"[{idx + 1}/{total}] Classifying ID: {record_id}")

            result = classify(
                text=service_text[:3000],
                historical_context=""
            )

            is_valid = validate_prediction(result)

            df.at[idx, "FirstComponent_AI"] = result.get("primary_component", "")
            df.at[idx, "SecondaryComponent_AI"] = result.get("secondary_component", "")
            df.at[idx, "FailureReason_AI"] = result.get("failure_reason", "")
            df.at[idx, "AI_Confidence"] = float(result.get("confidence", 0.0) or 0.0)
            df.at[idx, "AI_EvidencePhrases"] = "; ".join(result.get("evidence_phrases", []))
            df.at[idx, "AI_ReasoningSummary"] = result.get("reasoning_summary", "")
            df.at[idx, "AI_RawResponse"] = result.get("raw_response", "")

            if is_valid:
                df.at[idx, "AI_Status"] = "OK"
            else:
                df.at[idx, "AI_Status"] = "Invalid JSON structure"

        except Exception as e:
            df.at[idx, "AI_Status"] = f"Error: {e}"

        if (idx + 1) % CHECKPOINT_EVERY == 0:
            print(f"Checkpoint saved at row {idx + 1}")
            df.to_csv(OUTPUT_CSV, index=False)

        time.sleep(SLEEP_BETWEEN_CALLS)

    df.to_csv(OUTPUT_CSV, index=False)

    with pd.ExcelWriter(OUTPUT_XLSX, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="Full_AI_Output", index=False)

        update_cols = [
            PRIMARY_KEY_COL,
            CURRENT_PRIMARY_COL,
            CURRENT_SECONDARY_COL,
            CURRENT_REASON_COL,
            "FirstComponent_AI",
            "SecondaryComponent_AI",
            "FailureReason_AI",
            "AI_Confidence",
            "AI_Status",
        ]

        update_df = df[update_cols].copy()
        update_df.to_excel(writer, sheet_name="SQL_Update_Ready", index=False)

    print("Done.")
    print(f"CSV created: {OUTPUT_CSV}")
    print(f"Excel created: {OUTPUT_XLSX}")


if __name__ == "__main__":
    main()