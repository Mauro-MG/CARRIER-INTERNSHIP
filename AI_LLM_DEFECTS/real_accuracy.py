import pandas as pd

INPUT_XLSX = "independent_audit_results.xlsx"
OUTPUT_XLSX = "real_accuracy_results.xlsx"

SHEET = "AllRowsWithAudit"

PRIMARY_MATCH = "PrimaryMatch_v2"
SECONDARY_MATCH = "SecondaryMatch_v2"
REASON_MATCH = "ReasonMatch_v2"

PRIMARY_AUDIT_COL = "PrimaryAuditDecision"
SECONDARY_AUDIT_COL = "SecondaryAuditDecision"
REASON_AUDIT_COL = "ReasonAuditDecision"
OVERALL_AUDIT_COL = "IndependentAuditDecision"

VALID_RECOVERY = {
    "AGREEMENT",
    "MODEL_CORRECT",
    "LABEL_QUESTIONABLE",
    "BOTH_DEFENSIBLE",
    "NO_DISAGREEMENT",
}

def clean_decision(x):
    return str(x).strip().upper()

def main():
    df = pd.read_excel(INPUT_XLSX, sheet_name=SHEET)

    required = [
        PRIMARY_MATCH,
        SECONDARY_MATCH,
        REASON_MATCH,
        PRIMARY_AUDIT_COL,
        SECONDARY_AUDIT_COL,
        REASON_AUDIT_COL,
        OVERALL_AUDIT_COL,
        "DisagreementCount",
    ]

    for col in required:
        if col not in df.columns:
            raise ValueError(f"Missing column: {col}")

    for col in [
        PRIMARY_AUDIT_COL,
        SECONDARY_AUDIT_COL,
        REASON_AUDIT_COL,
        OVERALL_AUDIT_COL,
    ]:
        df[col] = df[col].apply(clean_decision)

    df["OriginalExactMatch"] = (
        df[PRIMARY_MATCH]
        & df[SECONDARY_MATCH]
        & df[REASON_MATCH]
    )

    df["RealPrimaryCorrect"] = (
        df[PRIMARY_MATCH]
        | df[PRIMARY_AUDIT_COL].isin(VALID_RECOVERY)
    )

    df["RealSecondaryCorrect"] = (
        df[SECONDARY_MATCH]
        | df[SECONDARY_AUDIT_COL].isin(VALID_RECOVERY)
    )

    df["RealReasonCorrect"] = (
        df[REASON_MATCH]
        | df[REASON_AUDIT_COL].isin(VALID_RECOVERY)
    )

    df["RealExactCorrect"] = (
        df["RealPrimaryCorrect"]
        & df["RealSecondaryCorrect"]
        & df["RealReasonCorrect"]
    )

    df["TruePrimaryError"] = ~df["RealPrimaryCorrect"]
    df["TrueSecondaryError"] = ~df["RealSecondaryCorrect"]
    df["TrueReasonError"] = ~df["RealReasonCorrect"]

    df["PrimaryRecovered"] = (
        (~df[PRIMARY_MATCH]) & df["RealPrimaryCorrect"]
    )
    df["SecondaryRecovered"] = (
        (~df[SECONDARY_MATCH]) & df["RealSecondaryCorrect"]
    )
    df["ReasonRecovered"] = (
        (~df[REASON_MATCH]) & df["RealReasonCorrect"]
    )

    summary = pd.DataFrame([
        {"Metric": "Total rows", "Value": len(df)},

        {"Metric": "Original Primary Accuracy", "Value": df[PRIMARY_MATCH].mean()},
        {"Metric": "Original Secondary Accuracy", "Value": df[SECONDARY_MATCH].mean()},
        {"Metric": "Original Reason Accuracy", "Value": df[REASON_MATCH].mean()},
        {"Metric": "Original Exact Accuracy", "Value": df["OriginalExactMatch"].mean()},

        {"Metric": "Real Primary Accuracy", "Value": df["RealPrimaryCorrect"].mean()},
        {"Metric": "Real Secondary Accuracy", "Value": df["RealSecondaryCorrect"].mean()},
        {"Metric": "Real Reason Accuracy", "Value": df["RealReasonCorrect"].mean()},
        {"Metric": "Real Exact Accuracy", "Value": df["RealExactCorrect"].mean()},

        {"Metric": "Recovered Primary Rows", "Value": int(df["PrimaryRecovered"].sum())},
        {"Metric": "Recovered Secondary Rows", "Value": int(df["SecondaryRecovered"].sum())},
        {"Metric": "Recovered Reason Rows", "Value": int(df["ReasonRecovered"].sum())},

        {"Metric": "True Primary Errors", "Value": int(df["TruePrimaryError"].sum())},
        {"Metric": "True Secondary Errors", "Value": int(df["TrueSecondaryError"].sum())},
        {"Metric": "True Reason Errors", "Value": int(df["TrueReasonError"].sum())},

        {"Metric": "Rows with 0 mistakes", "Value": int((df["DisagreementCount"] == 0).sum())},
        {"Metric": "Rows with 1 mistake", "Value": int((df["DisagreementCount"] == 1).sum())},
        {"Metric": "Rows with 2+ mistakes", "Value": int((df["DisagreementCount"] >= 2).sum())},
    ])

    primary_summary = df[PRIMARY_AUDIT_COL].value_counts(dropna=False).reset_index()
    primary_summary.columns = ["PrimaryAuditDecision", "Count"]
    primary_summary["Percent"] = primary_summary["Count"] / len(df)

    secondary_summary = df[SECONDARY_AUDIT_COL].value_counts(dropna=False).reset_index()
    secondary_summary.columns = ["SecondaryAuditDecision", "Count"]
    secondary_summary["Percent"] = secondary_summary["Count"] / len(df)

    reason_summary = df[REASON_AUDIT_COL].value_counts(dropna=False).reset_index()
    reason_summary.columns = ["ReasonAuditDecision", "Count"]
    reason_summary["Percent"] = reason_summary["Count"] / len(df)

    overall_summary = df[OVERALL_AUDIT_COL].value_counts(dropna=False).reset_index()
    overall_summary.columns = ["IndependentAuditDecision", "Count"]
    overall_summary["Percent"] = overall_summary["Count"] / len(df)

    with pd.ExcelWriter(OUTPUT_XLSX, engine="openpyxl") as writer:
        summary.to_excel(writer, sheet_name="Summary", index=False)
        overall_summary.to_excel(writer, sheet_name="OverallAuditSummary", index=False)
        primary_summary.to_excel(writer, sheet_name="PrimaryAuditSummary", index=False)
        secondary_summary.to_excel(writer, sheet_name="SecondaryAuditSummary", index=False)
        reason_summary.to_excel(writer, sheet_name="ReasonAuditSummary", index=False)

        df.to_excel(writer, sheet_name="AllRowsWithRealAccuracy", index=False)
        df[df["TruePrimaryError"]].to_excel(writer, sheet_name="TruePrimaryErrors", index=False)
        df[df["TrueSecondaryError"]].to_excel(writer, sheet_name="TrueSecondaryErrors", index=False)
        df[df["TrueReasonError"]].to_excel(writer, sheet_name="TrueReasonErrors", index=False)

    print(f"Created: {OUTPUT_XLSX}")
    print(summary.to_string(index=False))

if __name__ == "__main__":
    main()