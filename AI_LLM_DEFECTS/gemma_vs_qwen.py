import pandas as pd
import time
from sklearn.metrics import classification_report

from classifierv4 import classify
from best_gema_config import (
    PRIMARY_COMPONENTS,
    SECONDARY_COMPONENTS,
    FAILURE_REASONS,
    map_secondary_group,
    normalize_secondary,
)

INPUT_XLSX = "test_set_qwen.xlsx"
INPUT_SHEET = 0
OUTPUT_XLSX = "qwen_vs_gemma_comparison.xlsx"

MODEL = "gemma4:12B"  # remove extra space

SERVICE_COL = "service_text"
PART_COL = "ReplacementPartDescription"

REAL_PRIMARY_COL = "actual_primary"
REAL_SECONDARY_COL = "actual_secondary"
REAL_REASON_COL = "actual_failure"

QWEN_PRIMARY_COL = "pred_primary_qwen"
QWEN_SECONDARY_COL = "pred_secondary_qwen"
QWEN_REASON_COL = "pred_failure_qwen "

QWEN_PRIMARY_MATCH_COL = "primary_match_qwen"
QWEN_SECONDARY_MATCH_COL = "secondary_match_qwen"
QWEN_REASON_MATCH_COL = "failure_match_qwen"


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

    return text in {"TRUE", "1", "YES", "Y"}


def main():
    overall_start = time.perf_counter()

    df = pd.read_excel(INPUT_XLSX, sheet_name=INPUT_SHEET)

    required_cols = [
        SERVICE_COL,
        REAL_PRIMARY_COL,
        REAL_SECONDARY_COL,
        REAL_REASON_COL,
        QWEN_PRIMARY_COL,
        QWEN_SECONDARY_COL,
        QWEN_REASON_COL,
    ]

    for col in required_cols:
        if col not in df.columns:
            raise ValueError(f"Missing required column: {col}")

    if PART_COL not in df.columns:
        df[PART_COL] = ""

    # Normalize actual labels
    df[REAL_PRIMARY_COL] = df[REAL_PRIMARY_COL].apply(
        lambda x: normalize_to_taxonomy(x, PRIMARY_COMPONENTS)
    )
    df[REAL_SECONDARY_COL] = df[REAL_SECONDARY_COL].apply(
        lambda x: normalize_to_taxonomy(x, SECONDARY_COMPONENTS)
    )
    df[REAL_REASON_COL] = df[REAL_REASON_COL].apply(
        lambda x: normalize_to_taxonomy(x, FAILURE_REASONS)
    )

    # Normalize Qwen predictions
    df[QWEN_PRIMARY_COL] = df[QWEN_PRIMARY_COL].apply(
        lambda x: normalize_to_taxonomy(x, PRIMARY_COMPONENTS)
    )
    df[QWEN_SECONDARY_COL] = df[QWEN_SECONDARY_COL].apply(
        lambda x: normalize_to_taxonomy(x, SECONDARY_COMPONENTS)
    )
    df[QWEN_REASON_COL] = df[QWEN_REASON_COL].apply(
        lambda x: normalize_to_taxonomy(x, FAILURE_REASONS)
    )

    # Recalculate Qwen matches to make sure they use same normalization
    df[QWEN_PRIMARY_MATCH_COL] = (
        df[QWEN_PRIMARY_COL].apply(normalize_key)
        == df[REAL_PRIMARY_COL].apply(normalize_key)
    )

    df[QWEN_SECONDARY_MATCH_COL] = (
        df[QWEN_SECONDARY_COL].apply(normalize_key)
        == df[REAL_SECONDARY_COL].apply(normalize_key)
    )

    df[QWEN_REASON_MATCH_COL] = (
        df[QWEN_REASON_COL].apply(normalize_key)
        == df[REAL_REASON_COL].apply(normalize_key)
    )

    # New Gemma columns
    df["pred_primary_gemma"] = ""
    df["pred_secondary_gemma"] = ""
    df["pred_failure_gemma"] = ""
    df["primary_match_gemma"] = False
    df["secondary_match_gemma"] = False
    df["failure_match_gemma"] = False
    df["gemma_model_used"] = ""
    df["gemma_confidence"] = 0.0

    df = df[
        df[SERVICE_COL].notna()
        & (df[SERVICE_COL].astype(str).str.strip() != "")
    ].copy()

    print(f"Rows to process with Gemma: {len(df)}")

    for counter, (idx, row) in enumerate(df.iterrows(), start=1):
        print(f"[{counter}/{len(df)}] Running Gemma on index {idx}")

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
            print(f"   ! Empty result at index {idx}. Retrying with llama3.")
            result = classify(
                text=service_text,
                replacement_part_description=replacement_part,
                model="llama3",
            )

        pred_primary = normalize_to_taxonomy(
            result.get("primary_component", ""),
            PRIMARY_COMPONENTS,
        )

        pred_secondary = normalize_to_taxonomy(
            result.get("secondary_component", ""),
            SECONDARY_COMPONENTS,
        )

        pred_reason = normalize_to_taxonomy(
            result.get("failure_reason", ""),
            FAILURE_REASONS,
        )

        df.at[idx, "pred_primary_gemma"] = pred_primary
        df.at[idx, "pred_secondary_gemma"] = pred_secondary
        df.at[idx, "pred_failure_gemma"] = pred_reason

        df.at[idx, "primary_match_gemma"] = (
            normalize_key(pred_primary) == normalize_key(row[REAL_PRIMARY_COL])
        )

        df.at[idx, "secondary_match_gemma"] = (
            normalize_key(pred_secondary) == normalize_key(row[REAL_SECONDARY_COL])
        )

        df.at[idx, "failure_match_gemma"] = (
            normalize_key(pred_reason) == normalize_key(row[REAL_REASON_COL])
        )

        df.at[idx, "gemma_model_used"] = result.get("model_used", MODEL)
        df.at[idx, "gemma_confidence"] = float(result.get("confidence", 0.0) or 0.0)

    # Exact match columns
    df["exact_match_qwen"] = (
        df[QWEN_PRIMARY_MATCH_COL]
        & df[QWEN_SECONDARY_MATCH_COL]
        & df[QWEN_REASON_MATCH_COL]
    )

    df["exact_match_gemma"] = (
        df["primary_match_gemma"]
        & df["secondary_match_gemma"]
        & df["failure_match_gemma"]
    )

    # Side-by-side summary
    summary_df = pd.DataFrame([
        {
            "Metric": "Primary Accuracy",
            "Qwen": df[QWEN_PRIMARY_MATCH_COL].mean(),
            "Gemma": df["primary_match_gemma"].mean(),
            "Delta_Gemma_minus_Qwen": df["primary_match_gemma"].mean() - df[QWEN_PRIMARY_MATCH_COL].mean(),
        },
        {
            "Metric": "Secondary Accuracy",
            "Qwen": df[QWEN_SECONDARY_MATCH_COL].mean(),
            "Gemma": df["secondary_match_gemma"].mean(),
            "Delta_Gemma_minus_Qwen": df["secondary_match_gemma"].mean() - df[QWEN_SECONDARY_MATCH_COL].mean(),
        },
        {
            "Metric": "Failure Reason Accuracy",
            "Qwen": df[QWEN_REASON_MATCH_COL].mean(),
            "Gemma": df["failure_match_gemma"].mean(),
            "Delta_Gemma_minus_Qwen": df["failure_match_gemma"].mean() - df[QWEN_REASON_MATCH_COL].mean(),
        },
        {
            "Metric": "Exact Match Accuracy",
            "Qwen": df["exact_match_qwen"].mean(),
            "Gemma": df["exact_match_gemma"].mean(),
            "Delta_Gemma_minus_Qwen": df["exact_match_gemma"].mean() - df["exact_match_qwen"].mean(),
        },
    ])

    # Useful comparison sheets
    qwen_only_correct = df[
        (df["exact_match_qwen"])
        & (~df["exact_match_gemma"])
    ].copy()

    gemma_only_correct = df[
        (~df["exact_match_qwen"])
        & (df["exact_match_gemma"])
    ].copy()

    both_wrong = df[
        (~df["exact_match_qwen"])
        & (~df["exact_match_gemma"])
    ].copy()

    both_correct = df[
        (df["exact_match_qwen"])
        & (df["exact_match_gemma"])
    ].copy()

    print("\n=== QWEN VS GEMMA RESULTS ===")
    print(summary_df.to_string(index=False))

    print("\nGemma Primary Report")
    print(classification_report(
        df[REAL_PRIMARY_COL],
        df["pred_primary_gemma"],
        zero_division=0
    ))

    print("\nGemma Secondary Report")
    print(classification_report(
        df[REAL_SECONDARY_COL],
        df["pred_secondary_gemma"],
        zero_division=0
    ))

    print("\nGemma Failure Reason Report")
    print(classification_report(
        df[REAL_REASON_COL],
        df["pred_failure_gemma"],
        zero_division=0
    ))

    with pd.ExcelWriter(OUTPUT_XLSX, engine="openpyxl") as writer:
        summary_df.to_excel(writer, sheet_name="Summary", index=False)
        df.to_excel(writer, sheet_name="Comparison_All_Rows", index=False)
        qwen_only_correct.to_excel(writer, sheet_name="QwenOnlyCorrect", index=False)
        gemma_only_correct.to_excel(writer, sheet_name="GemmaOnlyCorrect", index=False)
        both_wrong.to_excel(writer, sheet_name="BothWrong", index=False)
        both_correct.to_excel(writer, sheet_name="BothCorrect", index=False)

    elapsed = (time.perf_counter() - overall_start) / 60
    print(f"\nTotal runtime: {elapsed:.2f} minutes")
    print(f"Excel created: {OUTPUT_XLSX}")


if __name__ == "__main__":
    main()