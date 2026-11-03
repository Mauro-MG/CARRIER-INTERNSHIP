import pandas as pd

INPUT_XLSX = "label_audit_model_reviewed.xlsx"
OUTPUT_XLSX = "real_accuracy_results.xlsx"

AUDIT_SHEET = "AuditReviewed"

DECISION_COL = "ModelAuditDecision"

PRIMARY_MATCH = "PrimaryMatch_v2"
SECONDARY_MATCH = "SecondaryMatch_v2"
REASON_MATCH = "ReasonMatch_v2"

NON_TRUE_ERRORS = {
    "MODEL_CORRECT",
    "BOTH_DEFENSIBLE",
    "LABEL_QUESTIONABLE",
}

TRUE_ERRORS = {
    "MODEL_WRONG",
}


def clean_decision(x):
    return str(x).strip().upper()


def main():
    df = pd.read_excel(INPUT_XLSX, sheet_name=AUDIT_SHEET)

    required = [
        DECISION_COL,
        PRIMARY_MATCH,
        SECONDARY_MATCH,
        REASON_MATCH,
    ]

    for col in required:
        if col not in df.columns:
            raise ValueError(f"Missing column: {col}")

    df[DECISION_COL] = df[DECISION_COL].apply(clean_decision)

    # Original benchmark accuracy
    df["OriginalExactMatch"] = (
        df[PRIMARY_MATCH]
        & df[SECONDARY_MATCH]
        & df[REASON_MATCH]
    )

    # Real/effective exact correctness:
    # exact match OR disagreement judged not to be a true model error
    df["EffectiveExactCorrect"] = (
        df["OriginalExactMatch"]
        | df[DECISION_COL].isin(NON_TRUE_ERRORS)
    )

    # True model error:
    df["TrueModelError"] = df[DECISION_COL].isin(TRUE_ERRORS)

    summary = pd.DataFrame([
        {"Metric": "Rows evaluated", "Value": len(df)},
        {"Metric": "Original exact match accuracy", "Value": df["OriginalExactMatch"].mean()},
        {"Metric": "Effective / real exact accuracy", "Value": df["EffectiveExactCorrect"].mean()},
        {"Metric": "True model error rate", "Value": df["TrueModelError"].mean()},
        {"Metric": "Recovered rows from audit", "Value": int(df[DECISION_COL].isin(NON_TRUE_ERRORS).sum())},
        {"Metric": "MODEL_WRONG rows", "Value": int((df[DECISION_COL] == "MODEL_WRONG").sum())},
        {"Metric": "MODEL_CORRECT rows", "Value": int((df[DECISION_COL] == "MODEL_CORRECT").sum())},
        {"Metric": "BOTH_DEFENSIBLE rows", "Value": int((df[DECISION_COL] == "BOTH_DEFENSIBLE").sum())},
        {"Metric": "LABEL_QUESTIONABLE rows", "Value": int((df[DECISION_COL] == "LABEL_QUESTIONABLE").sum())},
    ])

    decision_summary = (
        df[DECISION_COL]
        .value_counts(dropna=False)
        .reset_index()
    )
    decision_summary.columns = [DECISION_COL, "Count"]
    decision_summary["Percent"] = decision_summary["Count"] / len(df)

    with pd.ExcelWriter(OUTPUT_XLSX, engine="openpyxl") as writer:
        summary.to_excel(writer, sheet_name="Summary", index=False)
        decision_summary.to_excel(writer, sheet_name="DecisionSummary", index=False)
        df.to_excel(writer, sheet_name="RealAccuracyRows", index=False)
        df[df["TrueModelError"]].to_excel(writer, sheet_name="TrueModelErrors", index=False)
        df[df["EffectiveExactCorrect"]].to_excel(writer, sheet_name="EffectiveCorrect", index=False)

    print(f"Created: {OUTPUT_XLSX}")
    print(summary.to_string(index=False))
    print("\nDecision Summary:")
    print(decision_summary.to_string(index=False))


if __name__ == "__main__":
    main()