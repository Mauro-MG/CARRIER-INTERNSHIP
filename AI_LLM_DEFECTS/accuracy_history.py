import pandas as pd
import time
from classifierv3 import classify

INPUT_CSV = "data_historical_claims.csv"
OUTPUT_XLSX = "history_comparison_100_rows.xlsx"

SAMPLE_SIZE = 100
RANDOM_STATE = 42
MODEL = "gemma4:12b"

# Adjust these if your actual column names are different
SERIAL_COL = "Serial"
DATE_COL = "ClaimDate"
SERVICE_COL = "ServicePerformed"
PART_COL = "ReplacementPartDescription"

REAL_PRIMARY_COL = "Primary Component"
REAL_SECONDARY_COL = "Secondary Component code"
REAL_REASON_COL = "Failure Reason "


def clean(value):
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
    )


def build_related_history(df, current_idx, max_days=30, max_claims=5):
    row = df.loc[current_idx]

    serial = clean(row.get(SERIAL_COL, ""))
    current_date = row.get(DATE_COL)

    if not serial or pd.isna(current_date):
        return "Not Provided"

    start_date = current_date - pd.Timedelta(days=max_days)

    history_df = df[
        (df[SERIAL_COL].astype(str).str.strip() == serial)
        & (df[DATE_COL] < current_date)
        & (df[DATE_COL] >= start_date)
    ].copy()

    if history_df.empty:
        return "Not Provided"

    history_df = history_df.sort_values(DATE_COL).tail(max_claims)

    lines = []

    for _, hrow in history_df.iterrows():
        claim_date = hrow[DATE_COL]
        service = clean(hrow.get(SERVICE_COL, ""))

        if len(service) > 500:
            service = service[:500] + "..."

        lines.append(
            f"- {claim_date.date()}: {service}"
        )

    return "\n".join(lines)


def classify_without_history(service_text, replacement_part):
    return classify(
        text=service_text,
        replacement_part_description=replacement_part,
        related_claim_history="Not Provided",
        model=MODEL
    )


def classify_with_history(service_text, replacement_part, related_history):
    return classify(
        text=service_text,
        replacement_part_description=replacement_part,
        related_claim_history=related_history,
        model=MODEL
    )


def main():
    overall_start = time.perf_counter()

    df = pd.read_csv(INPUT_CSV)

    required_cols = [
        SERIAL_COL,
        DATE_COL,
        SERVICE_COL,
        REAL_PRIMARY_COL,
        REAL_SECONDARY_COL,
        REAL_REASON_COL,
    ]

    for col in required_cols:
        if col not in df.columns:
            raise ValueError(f"Missing required column: {col}")

    if PART_COL not in df.columns:
        df[PART_COL] = ""

    df[DATE_COL] = pd.to_datetime(df[DATE_COL], errors="coerce")

    df = df[
        df[SERVICE_COL].notna()
        & (df[SERVICE_COL].astype(str).str.strip() != "")
        & df[DATE_COL].notna()
        & df[SERIAL_COL].notna()
        & (df[SERIAL_COL].astype(str).str.strip() != "")
    ].copy()

    sample_df = df.sample(
        n=min(SAMPLE_SIZE, len(df)),
        random_state=RANDOM_STATE
    ).copy()

    print(f"Rows selected: {len(sample_df)}")

    results = []

    for counter, (idx, row) in enumerate(sample_df.iterrows(), start=1):
        print(f"\n[{counter}/{len(sample_df)}] Testing row index {idx}")

        service_text = clean(row.get(SERVICE_COL, ""))
        replacement_part = clean(row.get(PART_COL, "")) or "Not Provided"
        related_history = build_related_history(df, idx)

        real_primary = clean(row.get(REAL_PRIMARY_COL, ""))
        real_secondary = clean(row.get(REAL_SECONDARY_COL, ""))
        real_reason = clean(row.get(REAL_REASON_COL, ""))

        start_no_history = time.perf_counter()
        no_hist_result = classify_without_history(
            service_text,
            replacement_part
        )
        no_history_time = time.perf_counter() - start_no_history

        start_with_history = time.perf_counter()
        hist_result = classify_with_history(
            service_text,
            replacement_part,
            related_history
        )
        history_time = time.perf_counter() - start_with_history

        no_primary = no_hist_result.get("primary_component", "")
        no_secondary = no_hist_result.get("secondary_component", "")
        no_reason = no_hist_result.get("failure_reason", "")

        hist_primary = hist_result.get("primary_component", "")
        hist_secondary = hist_result.get("secondary_component", "")
        hist_reason = hist_result.get("failure_reason", "")

        no_primary_match = normalize_key(no_primary) == normalize_key(real_primary)
        no_secondary_match = normalize_key(no_secondary) == normalize_key(real_secondary)
        no_reason_match = normalize_key(no_reason) == normalize_key(real_reason)

        hist_primary_match = normalize_key(hist_primary) == normalize_key(real_primary)
        hist_secondary_match = normalize_key(hist_secondary) == normalize_key(real_secondary)
        hist_reason_match = normalize_key(hist_reason) == normalize_key(real_reason)

        results.append({
            "OriginalIndex": idx,
            "SerialNumber": clean(row.get(SERIAL_COL, "")),
            "ClaimDate": row.get(DATE_COL),

            "ServicePerformed": service_text,
            "ReplacementPartDescription": replacement_part,
            "RelatedClaimHistory": related_history,

            "RealPrimary": real_primary,
            "NoHistoryPrimary": no_primary,
            "WithHistoryPrimary": hist_primary,
            "NoHistoryPrimaryMatch": no_primary_match,
            "WithHistoryPrimaryMatch": hist_primary_match,

            "RealSecondary": real_secondary,
            "NoHistorySecondary": no_secondary,
            "WithHistorySecondary": hist_secondary,
            "NoHistorySecondaryMatch": no_secondary_match,
            "WithHistorySecondaryMatch": hist_secondary_match,

            "RealReason": real_reason,
            "NoHistoryReason": no_reason,
            "WithHistoryReason": hist_reason,
            "NoHistoryReasonMatch": no_reason_match,
            "WithHistoryReasonMatch": hist_reason_match,

            "NoHistoryCorrectCount": int(no_primary_match) + int(no_secondary_match) + int(no_reason_match),
            "WithHistoryCorrectCount": int(hist_primary_match) + int(hist_secondary_match) + int(hist_reason_match),

            "NoHistoryModelUsed": no_hist_result.get("model_used", MODEL),
            "WithHistoryModelUsed": hist_result.get("model_used", MODEL),

            "NoHistoryTimeSec": round(no_history_time, 2),
            "WithHistoryTimeSec": round(history_time, 2),
        })

    result_df = pd.DataFrame(results)

    summary = pd.DataFrame([
        {
            "Metric": "Primary Accuracy",
            "NoHistory": result_df["NoHistoryPrimaryMatch"].mean(),
            "WithHistory": result_df["WithHistoryPrimaryMatch"].mean(),
            "Delta": result_df["WithHistoryPrimaryMatch"].mean() - result_df["NoHistoryPrimaryMatch"].mean(),
        },
        {
            "Metric": "Secondary Accuracy",
            "NoHistory": result_df["NoHistorySecondaryMatch"].mean(),
            "WithHistory": result_df["WithHistorySecondaryMatch"].mean(),
            "Delta": result_df["WithHistorySecondaryMatch"].mean() - result_df["NoHistorySecondaryMatch"].mean(),
        },
        {
            "Metric": "Reason Accuracy",
            "NoHistory": result_df["NoHistoryReasonMatch"].mean(),
            "WithHistory": result_df["WithHistoryReasonMatch"].mean(),
            "Delta": result_df["WithHistoryReasonMatch"].mean() - result_df["NoHistoryReasonMatch"].mean(),
        },
        {
            "Metric": "Exact Match",
            "NoHistory": (result_df["NoHistoryCorrectCount"] == 3).mean(),
            "WithHistory": (result_df["WithHistoryCorrectCount"] == 3).mean(),
            "Delta": (result_df["WithHistoryCorrectCount"] == 3).mean() - (result_df["NoHistoryCorrectCount"] == 3).mean(),
        },
    ])

    changed_rows = result_df[
        (result_df["NoHistoryPrimary"] != result_df["WithHistoryPrimary"])
        | (result_df["NoHistorySecondary"] != result_df["WithHistorySecondary"])
        | (result_df["NoHistoryReason"] != result_df["WithHistoryReason"])
    ].copy()

    improved_rows = result_df[
        result_df["WithHistoryCorrectCount"] > result_df["NoHistoryCorrectCount"]
    ].copy()

    worsened_rows = result_df[
        result_df["WithHistoryCorrectCount"] < result_df["NoHistoryCorrectCount"]
    ].copy()

    with pd.ExcelWriter(OUTPUT_XLSX, engine="openpyxl") as writer:
        summary.to_excel(writer, sheet_name="Summary", index=False)
        result_df.to_excel(writer, sheet_name="Results", index=False)
        changed_rows.to_excel(writer, sheet_name="ChangedRows", index=False)
        improved_rows.to_excel(writer, sheet_name="ImprovedRows", index=False)
        worsened_rows.to_excel(writer, sheet_name="WorsenedRows", index=False)

    elapsed_min = (time.perf_counter() - overall_start) / 60

    print(f"\nCreated: {OUTPUT_XLSX}")
    print(f"Total runtime: {elapsed_min:.2f} minutes")
    print("\nSummary:")
    print(summary.to_string(index=False))


if __name__ == "__main__":
    main()