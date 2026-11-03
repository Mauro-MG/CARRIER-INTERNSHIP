import pandas as pd
from classifier import classify

INPUT_CSV = "data_historical_claims.csv"
OUTPUT_XLSX = "llama3_v2_benchmark_100_serials.xlsx"

SERIAL_SAMPLE_SIZE = 100
GROUP_WINDOW_DAYS = 1000
RANDOM_STATE = 42


# Change these if your current model columns have different names
CURRENT_PRIMARY_COL = "FirstComponentPred"
CURRENT_SECONDARY_COL = "SecondaryComponentPred"
CURRENT_REASON_COL = "FailureReasonPred"


def clean_text(value):
    if pd.isna(value):
        return ""
    return str(value).strip()


def group_claims_by_serial_6_months(df):
    df = df.copy()
    df["ClaimDate"] = pd.to_datetime(df["ClaimDate"], errors="coerce")
    df = df.sort_values(["Serial", "ClaimDate"]).reset_index(drop=True)

    grouped_rows = []

    for serial, serial_df in df.groupby("Serial"):
        serial_df = serial_df.sort_values("ClaimDate").reset_index(drop=True)

        current_group = []

        for _, row in serial_df.iterrows():
            if not current_group:
                current_group.append(row)
                continue

            group_dates = [r["ClaimDate"] for r in current_group]
            new_min = min(min(group_dates), row["ClaimDate"])
            new_max = max(max(group_dates), row["ClaimDate"])

            if (new_max - new_min).days <= GROUP_WINDOW_DAYS:
                current_group.append(row)
            else:
                grouped_rows.append(current_group)
                current_group = [row]

        if current_group:
            grouped_rows.append(current_group)

    final_rows = []

    for group in grouped_rows:
        group_df = pd.DataFrame(group).sort_values("ClaimDate")

        latest_row = group_df.iloc[-1].copy()

        merged_service = []

        for _, r in group_df.iterrows():
            merged_service.append(
                f"ClaimNumber: {r.get('ClaimNumber', '')}\n"
                f"Plant: {r.get('Plant', '')}\n"
                f"ClaimDate: {r.get('ClaimDate', '')}\n"
                f"ServicePerformed:\n{clean_text(r.get('ServicePerformed', ''))}"
            )

        latest_claim = group_df.iloc[-1]

        older_claims = group_df.iloc[:-1]

        older_context_parts = []

        for _, r in older_claims.iterrows():
            older_context_parts.append(
                f"""
        OLDER RELATED CLAIM
        ClaimNumber: {r.get('ClaimNumber', '')}
        ClaimDate: {r.get('ClaimDate', '')}
        ServicePerformed:
        {clean_text(r.get('ServicePerformed', ''))}
        """
            )

        latest_text = f"""
        MOST RECENT CLAIM - CLASSIFY THIS CLAIM
        ClaimNumber: {latest_claim.get('ClaimNumber', '')}
        ClaimDate: {latest_claim.get('ClaimDate', '')}
        ServicePerformed:
        {clean_text(latest_claim.get('ServicePerformed', ''))}
        """

        latest_row["ServicePerformed_Target"] = latest_text.strip()
        latest_row["HistoricalContext"] = "\n---\n".join(older_context_parts)

        latest_row["GroupedClaimNumbers"] = ", ".join(group_df["ClaimNumber"].astype(str).tolist())
        latest_row["GroupedClaimCount"] = len(group_df)
        latest_row["GroupMinClaimDate"] = group_df["ClaimDate"].min()
        latest_row["GroupMaxClaimDate"] = group_df["ClaimDate"].max()

        final_rows.append(latest_row)

    return pd.DataFrame(final_rows).reset_index(drop=True)


def main():
    df = pd.read_csv(INPUT_CSV)

    required_cols = [
        "Serial",
        "ClaimNumber",
        "ClaimDate",
        "Plant",
        "ServicePerformed",
        CURRENT_PRIMARY_COL,
        CURRENT_SECONDARY_COL,
        CURRENT_REASON_COL,
    ]

    for col in required_cols:
        if col not in df.columns:
            raise ValueError(f"Missing required column: {col}")

    df["ClaimDate"] = pd.to_datetime(df["ClaimDate"], errors="coerce")

    df = df[
        df["Serial"].notna()
        & df["ClaimNumber"].notna()
        & df["ClaimDate"].notna()
        & df["Plant"].notna()
        & df["ServicePerformed"].notna()
        & (df["ServicePerformed"].astype(str).str.strip() != "")
    ].copy()
    # STEP 1:
    # Balanced random sampling by Plant
    # Minimum 25 rows per plant if available

    MIN_PER_PLANT = 25

    sampled_parts = []

    plants = df["Plant"].dropna().unique()

    for plant in plants:

        plant_df = df[df["Plant"] == plant].copy()

        if len(plant_df) == 0:
            continue

        sample_n = min(MIN_PER_PLANT, len(plant_df))

        sampled_plant = plant_df.sample(
            n=sample_n,
            random_state=RANDOM_STATE
        )

        sampled_parts.append(sampled_plant)

    sampled_df = pd.concat(sampled_parts).reset_index(drop=True)

    print("\nSample counts by Plant:")
    print(sampled_df["Plant"].value_counts())

    # STEP 2:
    # Group ONLY inside sampled subset

    grouped_df = group_claims_by_serial_6_months(sampled_df)


    grouped_df["FirstComponentPred2"] = ""
    grouped_df["SecondaryComponentPred2"] = ""
    grouped_df["FailureReasonPred2"] = ""
    grouped_df["ConfidencePred2"] = 0.0
    grouped_df["EvidencePred2"] = ""
    grouped_df["ReasoningSummaryPred2"] = ""

    for idx, row in grouped_df.iterrows():
        print(
            f"Classifying Serial: {row['Serial']} | "
            f"Claims: {row['GroupedClaimNumbers']} | "
            f"Grouped count: {row['GroupedClaimCount']}"
        )
        target_text = str(row["ServicePerformed_Target"])[:2500]
        history_text = str(row["HistoricalContext"])[:4000]

        result = classify(
            text=target_text,
            historical_context=history_text
        )

        grouped_df.at[idx, "FirstComponentPred2"] = result.get("primary_component", "")
        grouped_df.at[idx, "SecondaryComponentPred2"] = result.get("secondary_component", "")
        grouped_df.at[idx, "FailureReasonPred2"] = result.get("failure_reason", "")
        grouped_df.at[idx, "ConfidencePred2"] = float(result.get("confidence", 0.0) or 0.0)
        grouped_df.at[idx, "EvidencePred2"] = "; ".join(result.get("evidence_phrases", []))
        grouped_df.at[idx, "ReasoningSummaryPred2"] = result.get("reasoning_summary", "")

    comparison_cols = [
    "Serial",
    "Plant",
    "GroupedClaimNumbers",
    "GroupedClaimCount",
    "GroupMinClaimDate",
    "GroupMaxClaimDate",

    CURRENT_PRIMARY_COL,
    CURRENT_SECONDARY_COL,
    CURRENT_REASON_COL,

    "FirstComponentPred2",
    "SecondaryComponentPred2",
    "FailureReasonPred2",
    "ConfidencePred2",
    "EvidencePred2",
    "ReasoningSummaryPred2",

    "ServicePerformed_Target",
    "HistoricalContext",
]
    comparison_df = grouped_df[comparison_cols].copy()

    with pd.ExcelWriter(OUTPUT_XLSX, engine="openpyxl") as writer:
        comparison_df.to_excel(writer, sheet_name="Comparison", index=False)
        grouped_df.to_excel(writer, sheet_name="Full_Output", index=False)

    print(f"Done. Output created: {OUTPUT_XLSX}")
    print(f"Random raw rows sampled: {len(sampled_df)}")
    print(f"Rows after grouping within sampled subset: {len(grouped_df)}")
    print(f"Rows after serial 6-month grouping: {len(grouped_df)}")


if __name__ == "__main__":
    main()