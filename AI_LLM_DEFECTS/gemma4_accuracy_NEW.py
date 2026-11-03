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

INPUT_CSV = "WarrantyTrainningSet.csv"
OUTPUT_XLSX = "accuracy_validation_all_rows.xlsx"

SAMPLE_SIZE = 389
RANDOM_STATE = 42
MODEL = "gemma4:12B "

REAL_PRIMARY_COL = "Primary Component"
REAL_SECONDARY_COL = "Secondary Component code"
REAL_REASON_COL = "Failure Reason "

CURRENT_PRIMARY_COL = "FirstComponentPred"
CURRENT_SECONDARY_COL = "SecondaryComponentPred"
CURRENT_REASON_COL = "FailureReasonPred"


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


def main():
    overall_start = time.perf_counter()
    df = pd.read_csv(INPUT_CSV)

    required_cols = [
        REAL_PRIMARY_COL,
        REAL_SECONDARY_COL,
        REAL_REASON_COL,
        SERVICE_COL := "ServicePerformed",
    ]

    for col in required_cols:
        if col not in df.columns:
            raise ValueError(f"Missing required column: {col}")

    if "ReplacementPartDescription" not in df.columns:
        df["ReplacementPartDescription"] = ""

    for col, tax in [
        (REAL_PRIMARY_COL, PRIMARY_COMPONENTS),
        (REAL_SECONDARY_COL, SECONDARY_COMPONENTS),
        (REAL_REASON_COL, FAILURE_REASONS),
        (CURRENT_PRIMARY_COL, PRIMARY_COMPONENTS),
        (CURRENT_SECONDARY_COL, SECONDARY_COMPONENTS),
        (CURRENT_REASON_COL, FAILURE_REASONS),
    ]:
        if col in df.columns:
            df[col] = df[col].apply(lambda x: normalize_to_taxonomy(x, tax))

    df = df[
        df["ServicePerformed"].notna()
        & (df["ServicePerformed"].astype(str).str.strip() != "")
    ].copy()

    sample_df = df.sample(
        n=min(SAMPLE_SIZE, len(df)),
        random_state=RANDOM_STATE
    ).copy()

    print(f"Rows selected for benchmark: {len(sample_df)}")

    sample_df["FirstComponentPred2"] = ""
    sample_df["SecondaryComponentPred2"] = ""
    sample_df["FailureReasonPred2"] = ""
    sample_df["ModelUsedPred2"] = ""
    sample_df["ConfidencePred2"] = 0.0

    for counter, (idx, row) in enumerate(sample_df.iterrows(), start=1):
        print(f"[{idx} - {counter}/{len(sample_df)}] Running benchmark on {MODEL}")

        service_text = clean_text(row["ServicePerformed"])
        replacement_part = clean_text(row.get("ReplacementPartDescription", "")) or "Not Provided"

        result = classify(
            text=service_text,
            replacement_part_description=replacement_part,
            model=MODEL
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
                model="llama3"
            )

        sample_df.at[idx, "FirstComponentPred2"] = normalize_to_taxonomy(
            result.get("primary_component", ""),
            PRIMARY_COMPONENTS
        )

        sample_df.at[idx, "SecondaryComponentPred2"] = normalize_to_taxonomy(
            result.get("secondary_component", ""),
            SECONDARY_COMPONENTS
        )

        sample_df.at[idx, "FailureReasonPred2"] = normalize_to_taxonomy(
            result.get("failure_reason", ""),
            FAILURE_REASONS
        )
        sample_df.at[idx, "ConfidencePred2"] = float(
            result.get("confidence", 0.0) or 0.0
        )

        sample_df.at[idx, "ModelUsedPred2"] = result.get("model_used", MODEL)

    sample_df["PrimaryMatch_v2"] = (
        sample_df["FirstComponentPred2"].apply(normalize_key)
        == sample_df[REAL_PRIMARY_COL].apply(normalize_key)
    )

    sample_df["SecondaryMatch_v2"] = (
        sample_df["SecondaryComponentPred2"].apply(normalize_key)
        == sample_df[REAL_SECONDARY_COL].apply(normalize_key)
    )

    sample_df["ReasonMatch_v2"] = (
        sample_df["FailureReasonPred2"].apply(normalize_key)
        == sample_df[REAL_REASON_COL].apply(normalize_key)
    )

    if CURRENT_PRIMARY_COL in sample_df.columns:
        sample_df["PrimaryMatch_v1"] = (
            sample_df[CURRENT_PRIMARY_COL].apply(normalize_key)
            == sample_df[REAL_PRIMARY_COL].apply(normalize_key)
        )
        sample_df["SecondaryMatch_v1"] = (
            sample_df[CURRENT_SECONDARY_COL].apply(normalize_key)
            == sample_df[REAL_SECONDARY_COL].apply(normalize_key)
        )
        sample_df["ReasonMatch_v1"] = (
            sample_df[CURRENT_REASON_COL].apply(normalize_key)
            == sample_df[REAL_REASON_COL].apply(normalize_key)
        )

    sample_df["IsAmbiguousPred"] = (
        sample_df["FirstComponentPred2"].apply(normalize_key) == "AMBIGUOUS"
    )

    useful_df = sample_df[~sample_df["IsAmbiguousPred"]].copy()

    summary_rows = [
        {
            "Metric": "Primary Accuracy",
            "Value": sample_df["PrimaryMatch_v2"].mean(),
        },
        {
            "Metric": "Secondary Accuracy",
            "Value": sample_df["SecondaryMatch_v2"].mean(),
        },
        {
            "Metric": "Reason Accuracy",
            "Value": sample_df["ReasonMatch_v2"].mean(),
        },
        {
            "Metric": "Exact Match Accuracy",
            "Value": (
                sample_df["PrimaryMatch_v2"]
                & sample_df["SecondaryMatch_v2"]
                & sample_df["ReasonMatch_v2"]
            ).mean(),
        },
        {
            "Metric": "Ambiguous Rate",
            "Value": sample_df["IsAmbiguousPred"].mean(),
        },
        {
            "Metric": "Coverage",
            "Value": 1 - sample_df["IsAmbiguousPred"].mean(),
        },
    ]

    if len(useful_df) > 0:
        summary_rows.extend([
            {
                "Metric": "Useful Primary Accuracy",
                "Value": useful_df["PrimaryMatch_v2"].mean(),
            },
            {
                "Metric": "Useful Secondary Accuracy",
                "Value": useful_df["SecondaryMatch_v2"].mean(),
            },
            {
                "Metric": "Useful Reason Accuracy",
                "Value": useful_df["ReasonMatch_v2"].mean(),
            },
        ])

    summary_df = pd.DataFrame(summary_rows)

    print("\n=== GEMMA4 RESULTS ===")
    print(summary_df.to_string(index=False))

    print("\nPrimary Classification Report")
    print(classification_report(
        sample_df[REAL_PRIMARY_COL],
        sample_df["FirstComponentPred2"],
        zero_division=0
    ))

    print("\nSecondary Classification Report")
    print(classification_report(
        sample_df[REAL_SECONDARY_COL],
        sample_df["SecondaryComponentPred2"],
        zero_division=0
    ))

    print("\nReason Classification Report")
    print(classification_report(
        sample_df[REAL_REASON_COL],
        sample_df["FailureReasonPred2"],
        zero_division=0
    ))

    with pd.ExcelWriter(OUTPUT_XLSX, engine="openpyxl") as writer:
        summary_df.to_excel(writer, sheet_name="Summary", index=False)
        sample_df.to_excel(writer, sheet_name="Benchmark_Results", index=False)

        changed_or_wrong = sample_df[
            (~sample_df["PrimaryMatch_v2"])
            | (~sample_df["SecondaryMatch_v2"])
            | (~sample_df["ReasonMatch_v2"])
            | (sample_df["IsAmbiguousPred"])
        ].copy()

        changed_or_wrong.to_excel(writer, sheet_name="ReviewRows", index=False)

    elapsed = (time.perf_counter() - overall_start) / 60
    print(f"\nTotal runtime: {elapsed:.2f} minutes")
    print(f"Excel created: {OUTPUT_XLSX}")


if __name__ == "__main__":
    main()