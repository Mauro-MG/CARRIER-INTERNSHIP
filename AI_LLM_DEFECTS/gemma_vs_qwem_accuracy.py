import pandas as pd

ACCURACY_XLSX = "qwen_vs_gemma_comparison.xlsx"
ACCURACY_SHEET = "Comparison_All_Rows"

AUDIT_CSV = "gemma_vs_qwen.csv"

OUTPUT_XLSX = "qwen_vs_gemma_real_field_accuracy.xlsx"

REAL_CORRECT_DECISIONS = {
    "NO_DISAGREEMENT",
    "MODEL_CORRECT",
    "BOTH_DEFENSIBLE",
    "LABEL_QUESTIONABLE",
}

STRICT_CORRECT_DECISIONS = {
    "NO_DISAGREEMENT",
    "MODEL_CORRECT",
}

FIELD_MATCH_COLS = {
    "Primary": {
        "qwen": "primary_match_qwen",
        "gemma": "primary_match_gemma",
    },
    "Secondary": {
        "qwen": "secondary_match_qwen",
        "gemma": "secondary_match_gemma",
    },
    "Failure Reason": {
        "qwen": "failure_match_qwen",
        "gemma": "failure_match_gemma",
    },
}
STRICT_REAL_DECISIONS = {
    "NO_DISAGREEMENT",
    "MODEL_CORRECT",
}

DEFENSIBLE_REAL_DECISIONS = {
    "NO_DISAGREEMENT",
    "MODEL_CORRECT",
    "BOTH_DEFENSIBLE",
}

LABEL_ADJUSTED_REAL_DECISIONS = {
    "NO_DISAGREEMENT",
    "MODEL_CORRECT",
    "BOTH_DEFENSIBLE",
    "LABEL_QUESTIONABLE",
}

def clean_columns(df):
    df.columns = [str(c).strip() for c in df.columns]
    return df


def clean_text(value):
    if pd.isna(value):
        return ""
    return str(value).strip()


def clean_decision(value):
    if pd.isna(value):
        return ""
    return str(value).strip().upper()


def to_bool(value):
    if isinstance(value, bool):
        return value

    text = str(value).strip().upper()

    return text in {
        "TRUE",
        "1",
        "YES",
        "Y",
        "CORRECT",
    }


def pct(value):
    return round(value * 100, 2)


def main():
    accuracy_df = pd.read_excel(
        ACCURACY_XLSX,
        sheet_name=ACCURACY_SHEET
    )

    audit_df = pd.read_csv(AUDIT_CSV)

    accuracy_df = clean_columns(accuracy_df)
    audit_df = clean_columns(audit_df)

    required_accuracy_cols = [
        "index",
        "claim_number",
        "primary_match_qwen",
        "secondary_match_qwen",
        "failure_match_qwen",
        "primary_match_gemma",
        "secondary_match_gemma",
        "failure_match_gemma",
    ]

    required_audit_cols = [
        "index",
        "claim_number",
        "qwen_audit_decision",
        "gemma_audit_decision",
        "preferred_model",
        "label_quality",
        "audit_confidence",
        "audit_comment",
    ]

    for col in required_accuracy_cols:
        if col not in accuracy_df.columns:
            raise ValueError(
                f"Missing column in Excel file: {col}\n"
                f"Available Excel columns:\n{accuracy_df.columns.tolist()}"
            )

    for col in required_audit_cols:
        if col not in audit_df.columns:
            raise ValueError(
                f"Missing column in audit CSV: {col}\n"
                f"Available audit columns:\n{audit_df.columns.tolist()}"
            )

    # Create safe merge key
    accuracy_df["merge_index"] = accuracy_df["index"].astype(str).str.strip()
    audit_df["merge_index"] = audit_df["index"].astype(str).str.strip()

    audit_keep_cols = [
        "merge_index",
        "qwen_audit_decision",
        "gemma_audit_decision",
        "preferred_model",
        "label_quality",
        "audit_confidence",
        "audit_comment",
    ]

    merged_df = accuracy_df.merge(
        audit_df[audit_keep_cols],
        on="merge_index",
        how="left",
        validate="one_to_one",
    )

    # Clean raw match columns
    all_match_cols = [
        "primary_match_qwen",
        "secondary_match_qwen",
        "failure_match_qwen",
        "primary_match_gemma",
        "secondary_match_gemma",
        "failure_match_gemma",
    ]

    for col in all_match_cols:
        merged_df[col] = merged_df[col].apply(to_bool)

    # Clean audit columns
    for col in [
        "qwen_audit_decision",
        "gemma_audit_decision",
        "preferred_model",
        "label_quality",
        "audit_confidence",
    ]:
        merged_df[col] = merged_df[col].apply(clean_decision)

    # Raw exact match
    merged_df["exact_match_qwen"] = (
        merged_df["primary_match_qwen"]
        & merged_df["secondary_match_qwen"]
        & merged_df["failure_match_qwen"]
    )

    merged_df["exact_match_gemma"] = (
        merged_df["primary_match_gemma"]
        & merged_df["secondary_match_gemma"]
        & merged_df["failure_match_gemma"]
    )

    # If audit decision is missing but raw exact is correct, treat as no disagreement
    merged_df.loc[
        (merged_df["qwen_audit_decision"] == "")
        & (merged_df["exact_match_qwen"]),
        "qwen_audit_decision",
    ] = "NO_DISAGREEMENT"

    merged_df.loc[
        (merged_df["gemma_audit_decision"] == "")
        & (merged_df["exact_match_gemma"]),
        "gemma_audit_decision",
    ] = "NO_DISAGREEMENT"

    merged_df.loc[
        merged_df["qwen_audit_decision"] == "",
        "qwen_audit_decision",
    ] = "MISSING_AUDIT"

    merged_df.loc[
        merged_df["gemma_audit_decision"] == "",
        "gemma_audit_decision",
    ] = "MISSING_AUDIT"

    # --------------------------------------------------
    # Real field accuracy using row-level audit decision
    # --------------------------------------------------
    # Important:
    # This is row-level adjusted field accuracy.
    # If the audit says MODEL_CORRECT or BOTH_DEFENSIBLE,
    # the model's wrong raw fields are recovered for that row.
    # --------------------------------------------------
    # Raw exact match
    # --------------------------------------------------

    merged_df["exact_match_qwen"] = (
        merged_df["primary_match_qwen"]
        & merged_df["secondary_match_qwen"]
        & merged_df["failure_match_qwen"]
    )

    merged_df["exact_match_gemma"] = (
        merged_df["primary_match_gemma"]
        & merged_df["secondary_match_gemma"]
        & merged_df["failure_match_gemma"]
    )

    # --------------------------------------------------
    # If audit is missing but exact match is correct,
    # treat as NO_DISAGREEMENT
    # --------------------------------------------------

    merged_df.loc[
        (merged_df["qwen_audit_decision"] == "")
        & (merged_df["exact_match_qwen"]),
        "qwen_audit_decision",
    ] = "NO_DISAGREEMENT"

    merged_df.loc[
        (merged_df["gemma_audit_decision"] == "")
        & (merged_df["exact_match_gemma"]),
        "gemma_audit_decision",
    ] = "NO_DISAGREEMENT"

    merged_df.loc[
        merged_df["qwen_audit_decision"] == "",
        "qwen_audit_decision",
    ] = "MISSING_AUDIT"

    merged_df.loc[
        merged_df["gemma_audit_decision"] == "",
        "gemma_audit_decision",
    ] = "MISSING_AUDIT"

    # --------------------------------------------------
    # Create field-level real accuracy columns
    # --------------------------------------------------

    for field_name, cols in FIELD_MATCH_COLS.items():
        field_key = field_name.lower().replace(" ", "_")

        qwen_raw_col = cols["qwen"]
        gemma_raw_col = cols["gemma"]

        # Strict real accuracy
        merged_df[f"{field_key}_strict_real_correct_qwen"] = (
            merged_df[qwen_raw_col]
            | merged_df["qwen_audit_decision"].isin(STRICT_REAL_DECISIONS)
        )

        merged_df[f"{field_key}_strict_real_correct_gemma"] = (
            merged_df[gemma_raw_col]
            | merged_df["gemma_audit_decision"].isin(STRICT_REAL_DECISIONS)
        )

        # Defensible real accuracy
        merged_df[f"{field_key}_defensible_real_correct_qwen"] = (
            merged_df[qwen_raw_col]
            | merged_df["qwen_audit_decision"].isin(DEFENSIBLE_REAL_DECISIONS)
        )

        merged_df[f"{field_key}_defensible_real_correct_gemma"] = (
            merged_df[gemma_raw_col]
            | merged_df["gemma_audit_decision"].isin(DEFENSIBLE_REAL_DECISIONS)
        )

        # Label-adjusted accuracy
        merged_df[f"{field_key}_label_adjusted_correct_qwen"] = (
            merged_df[qwen_raw_col]
            | merged_df["qwen_audit_decision"].isin(LABEL_ADJUSTED_REAL_DECISIONS)
        )

        merged_df[f"{field_key}_label_adjusted_correct_gemma"] = (
            merged_df[gemma_raw_col]
            | merged_df["gemma_audit_decision"].isin(LABEL_ADJUSTED_REAL_DECISIONS)
        )

    # --------------------------------------------------
    # Create exact real accuracy columns
    # --------------------------------------------------

    merged_df["exact_strict_real_correct_qwen"] = (
        merged_df["exact_match_qwen"]
        | merged_df["qwen_audit_decision"].isin(STRICT_REAL_DECISIONS)
    )

    merged_df["exact_strict_real_correct_gemma"] = (
        merged_df["exact_match_gemma"]
        | merged_df["gemma_audit_decision"].isin(STRICT_REAL_DECISIONS)
    )

    merged_df["exact_defensible_real_correct_qwen"] = (
        merged_df["exact_match_qwen"]
        | merged_df["qwen_audit_decision"].isin(DEFENSIBLE_REAL_DECISIONS)
    )

    merged_df["exact_defensible_real_correct_gemma"] = (
        merged_df["exact_match_gemma"]
        | merged_df["gemma_audit_decision"].isin(DEFENSIBLE_REAL_DECISIONS)
    )

    merged_df["exact_label_adjusted_correct_qwen"] = (
        merged_df["exact_match_qwen"]
        | merged_df["qwen_audit_decision"].isin(LABEL_ADJUSTED_REAL_DECISIONS)
    )

    merged_df["exact_label_adjusted_correct_gemma"] = (
        merged_df["exact_match_gemma"]
        | merged_df["gemma_audit_decision"].isin(LABEL_ADJUSTED_REAL_DECISIONS)
    )

    # --------------------------------------------------
    # Debug check: make sure columns were created
    # --------------------------------------------------

    expected_created_cols = []

    for field_name in FIELD_MATCH_COLS.keys():
        field_key = field_name.lower().replace(" ", "_")

        expected_created_cols.extend([
            f"{field_key}_strict_real_correct_qwen",
            f"{field_key}_strict_real_correct_gemma",
            f"{field_key}_defensible_real_correct_qwen",
            f"{field_key}_defensible_real_correct_gemma",
            f"{field_key}_label_adjusted_correct_qwen",
            f"{field_key}_label_adjusted_correct_gemma",
        ])

    expected_created_cols.extend([
        "exact_strict_real_correct_qwen",
        "exact_strict_real_correct_gemma",
        "exact_defensible_real_correct_qwen",
        "exact_defensible_real_correct_gemma",
        "exact_label_adjusted_correct_qwen",
        "exact_label_adjusted_correct_gemma",
    ])

    missing_created_cols = [
        col for col in expected_created_cols
        if col not in merged_df.columns
    ]

    if missing_created_cols:
        raise ValueError(
            "These real accuracy columns were not created:\n"
            + "\n".join(missing_created_cols)
        )

    # --------------------------------------------------
    # True error flags
    # --------------------------------------------------

    merged_df["qwen_true_error"] = merged_df["qwen_audit_decision"] == "MODEL_WRONG"
    merged_df["gemma_true_error"] = merged_df["gemma_audit_decision"] == "MODEL_WRONG"

    total_rows = len(merged_df)

    # --------------------------------------------------
    # Summary by field
    # --------------------------------------------------

    summary_rows = []

    for field_name, cols in FIELD_MATCH_COLS.items():
        field_key = field_name.lower().replace(" ", "_")

        qwen_raw_col = cols["qwen"]
        gemma_raw_col = cols["gemma"]

        qwen_raw_acc = merged_df[qwen_raw_col].mean()
        gemma_raw_acc = merged_df[gemma_raw_col].mean()

        qwen_strict_real_col = f"{field_key}_strict_real_correct_qwen"
        gemma_strict_real_col = f"{field_key}_strict_real_correct_gemma"

        qwen_defensible_real_col = f"{field_key}_defensible_real_correct_qwen"
        gemma_defensible_real_col = f"{field_key}_defensible_real_correct_gemma"

        qwen_label_adjusted_col = f"{field_key}_label_adjusted_correct_qwen"
        gemma_label_adjusted_col = f"{field_key}_label_adjusted_correct_gemma"

        qwen_strict_real_acc = merged_df[qwen_strict_real_col].mean()
        gemma_strict_real_acc = merged_df[gemma_strict_real_col].mean()

        qwen_defensible_real_acc = merged_df[qwen_defensible_real_col].mean()
        gemma_defensible_real_acc = merged_df[gemma_defensible_real_col].mean()

        qwen_label_adjusted_acc = merged_df[qwen_label_adjusted_col].mean()
        gemma_label_adjusted_acc = merged_df[gemma_label_adjusted_col].mean()

        summary_rows.append({
            "Field": field_name,
            "Rows": total_rows,

            "Qwen Raw Correct": int(merged_df[qwen_raw_col].sum()),
            "Qwen Raw Accuracy %": pct(qwen_raw_acc),

            "Gemma Raw Correct": int(merged_df[gemma_raw_col].sum()),
            "Gemma Raw Accuracy %": pct(gemma_raw_acc),

            "Raw Delta Gemma - Qwen %": pct(gemma_raw_acc - qwen_raw_acc),

            "Qwen Strict Real Correct": int(merged_df[qwen_strict_real_col].sum()),
            "Qwen Strict Real Accuracy %": pct(qwen_strict_real_acc),

            "Gemma Strict Real Correct": int(merged_df[gemma_strict_real_col].sum()),
            "Gemma Strict Real Accuracy %": pct(gemma_strict_real_acc),

            "Strict Real Delta Gemma - Qwen %": pct(
                gemma_strict_real_acc - qwen_strict_real_acc
            ),

            "Qwen Defensible Real Correct": int(merged_df[qwen_defensible_real_col].sum()),
            "Qwen Defensible Real Accuracy %": pct(qwen_defensible_real_acc),

            "Gemma Defensible Real Correct": int(merged_df[gemma_defensible_real_col].sum()),
            "Gemma Defensible Real Accuracy %": pct(gemma_defensible_real_acc),

            "Defensible Real Delta Gemma - Qwen %": pct(
                gemma_defensible_real_acc - qwen_defensible_real_acc
            ),

            "Qwen Label-Adjusted Correct": int(merged_df[qwen_label_adjusted_col].sum()),
            "Qwen Label-Adjusted Accuracy %": pct(qwen_label_adjusted_acc),

            "Gemma Label-Adjusted Correct": int(merged_df[gemma_label_adjusted_col].sum()),
            "Gemma Label-Adjusted Accuracy %": pct(gemma_label_adjusted_acc),

            "Label-Adjusted Delta Gemma - Qwen %": pct(
                gemma_label_adjusted_acc - qwen_label_adjusted_acc
            ),
        })

    # --------------------------------------------------
    # Exact match summary row
    # --------------------------------------------------

    summary_rows.append({
        "Field": "Exact Match",
        "Rows": total_rows,

        "Qwen Raw Correct": int(merged_df["exact_match_qwen"].sum()),
        "Qwen Raw Accuracy %": pct(merged_df["exact_match_qwen"].mean()),

        "Gemma Raw Correct": int(merged_df["exact_match_gemma"].sum()),
        "Gemma Raw Accuracy %": pct(merged_df["exact_match_gemma"].mean()),

        "Raw Delta Gemma - Qwen %": pct(
            merged_df["exact_match_gemma"].mean()
            - merged_df["exact_match_qwen"].mean()
        ),

        "Qwen Strict Real Correct": int(merged_df["exact_strict_real_correct_qwen"].sum()),
        "Qwen Strict Real Accuracy %": pct(merged_df["exact_strict_real_correct_qwen"].mean()),

        "Gemma Strict Real Correct": int(merged_df["exact_strict_real_correct_gemma"].sum()),
        "Gemma Strict Real Accuracy %": pct(merged_df["exact_strict_real_correct_gemma"].mean()),

        "Strict Real Delta Gemma - Qwen %": pct(
            merged_df["exact_strict_real_correct_gemma"].mean()
            - merged_df["exact_strict_real_correct_qwen"].mean()
        ),

        "Qwen Defensible Real Correct": int(merged_df["exact_defensible_real_correct_qwen"].sum()),
        "Qwen Defensible Real Accuracy %": pct(merged_df["exact_defensible_real_correct_qwen"].mean()),

        "Gemma Defensible Real Correct": int(merged_df["exact_defensible_real_correct_gemma"].sum()),
        "Gemma Defensible Real Accuracy %": pct(merged_df["exact_defensible_real_correct_gemma"].mean()),

        "Defensible Real Delta Gemma - Qwen %": pct(
            merged_df["exact_defensible_real_correct_gemma"].mean()
            - merged_df["exact_defensible_real_correct_qwen"].mean()
        ),

        "Qwen Label-Adjusted Correct": int(merged_df["exact_label_adjusted_correct_qwen"].sum()),
        "Qwen Label-Adjusted Accuracy %": pct(merged_df["exact_label_adjusted_correct_qwen"].mean()),

        "Gemma Label-Adjusted Correct": int(merged_df["exact_label_adjusted_correct_gemma"].sum()),
        "Gemma Label-Adjusted Accuracy %": pct(merged_df["exact_label_adjusted_correct_gemma"].mean()),

        "Label-Adjusted Delta Gemma - Qwen %": pct(
            merged_df["exact_label_adjusted_correct_gemma"].mean()
            - merged_df["exact_label_adjusted_correct_qwen"].mean()
        ),
    })

    summary_df = pd.DataFrame(summary_rows)

    # --------------------------------------------------
    # Audit summaries
    # --------------------------------------------------

    qwen_decision_summary = (
        merged_df["qwen_audit_decision"]
        .value_counts(dropna=False)
        .reset_index()
    )
    qwen_decision_summary.columns = ["qwen_audit_decision", "Count"]
    qwen_decision_summary["Percent"] = qwen_decision_summary["Count"] / total_rows
    qwen_decision_summary["Percent"] = qwen_decision_summary["Percent"].apply(pct)

    gemma_decision_summary = (
        merged_df["gemma_audit_decision"]
        .value_counts(dropna=False)
        .reset_index()
    )
    gemma_decision_summary.columns = ["gemma_audit_decision", "Count"]
    gemma_decision_summary["Percent"] = gemma_decision_summary["Count"] / total_rows
    gemma_decision_summary["Percent"] = gemma_decision_summary["Percent"].apply(pct)

    preferred_summary = (
        merged_df["preferred_model"]
        .value_counts(dropna=False)
        .reset_index()
    )
    preferred_summary.columns = ["preferred_model", "Count"]
    preferred_summary["Percent"] = preferred_summary["Count"] / total_rows
    preferred_summary["Percent"] = preferred_summary["Percent"].apply(pct)

    label_quality_summary = (
        merged_df["label_quality"]
        .value_counts(dropna=False)
        .reset_index()
    )
    label_quality_summary.columns = ["label_quality", "Count"]
    label_quality_summary["Percent"] = label_quality_summary["Count"] / total_rows
    label_quality_summary["Percent"] = label_quality_summary["Percent"].apply(pct)

    confidence_summary = (
        merged_df["audit_confidence"]
        .value_counts(dropna=False)
        .reset_index()
    )
    confidence_summary.columns = ["audit_confidence", "Count"]
    confidence_summary["Percent"] = confidence_summary["Count"] / total_rows
    confidence_summary["Percent"] = confidence_summary["Percent"].apply(pct)

    ## --------------------------------------------------
    # Useful row subsets
    # --------------------------------------------------

    # Strict real exact comparison
    qwen_only_strict_real_exact = merged_df[
        merged_df["exact_strict_real_correct_qwen"]
        & (~merged_df["exact_strict_real_correct_gemma"])
    ].copy()

    gemma_only_strict_real_exact = merged_df[
        (~merged_df["exact_strict_real_correct_qwen"])
        & merged_df["exact_strict_real_correct_gemma"]
    ].copy()

    both_strict_real_exact_correct = merged_df[
        merged_df["exact_strict_real_correct_qwen"]
        & merged_df["exact_strict_real_correct_gemma"]
    ].copy()

    both_strict_real_exact_wrong = merged_df[
        (~merged_df["exact_strict_real_correct_qwen"])
        & (~merged_df["exact_strict_real_correct_gemma"])
    ].copy()


    # Defensible real exact comparison
    qwen_only_defensible_real_exact = merged_df[
        merged_df["exact_defensible_real_correct_qwen"]
        & (~merged_df["exact_defensible_real_correct_gemma"])
    ].copy()

    gemma_only_defensible_real_exact = merged_df[
        (~merged_df["exact_defensible_real_correct_qwen"])
        & merged_df["exact_defensible_real_correct_gemma"]
    ].copy()

    both_defensible_real_exact_correct = merged_df[
        merged_df["exact_defensible_real_correct_qwen"]
        & merged_df["exact_defensible_real_correct_gemma"]
    ].copy()

    both_defensible_real_exact_wrong = merged_df[
        (~merged_df["exact_defensible_real_correct_qwen"])
        & (~merged_df["exact_defensible_real_correct_gemma"])
    ].copy()


    # Label-adjusted exact comparison
    qwen_only_label_adjusted_exact = merged_df[
        merged_df["exact_label_adjusted_correct_qwen"]
        & (~merged_df["exact_label_adjusted_correct_gemma"])
    ].copy()

    gemma_only_label_adjusted_exact = merged_df[
        (~merged_df["exact_label_adjusted_correct_qwen"])
        & merged_df["exact_label_adjusted_correct_gemma"]
    ].copy()
    # --------------------------------------------------
    # Export
    # --------------------------------------------------

    with pd.ExcelWriter(OUTPUT_XLSX, engine="openpyxl") as writer:
        summary_df.to_excel(writer, sheet_name="FieldAccuracySummary", index=False)

        qwen_decision_summary.to_excel(writer, sheet_name="QwenDecisionSummary", index=False)
        gemma_decision_summary.to_excel(writer, sheet_name="GemmaDecisionSummary", index=False)
        preferred_summary.to_excel(writer, sheet_name="PreferredModelSummary", index=False)
        label_quality_summary.to_excel(writer, sheet_name="LabelQualitySummary", index=False)
        confidence_summary.to_excel(writer, sheet_name="ConfidenceSummary", index=False)

        merged_df.to_excel(writer, sheet_name="AllRowsMerged", index=False)

        qwen_only_strict_real_exact.to_excel(writer, sheet_name="QwenOnlyStrictExact", index=False)
        gemma_only_strict_real_exact.to_excel(writer, sheet_name="GemmaOnlyStrictExact", index=False)
        both_strict_real_exact_correct.to_excel(writer, sheet_name="BothStrictExactCorrect", index=False)
        both_strict_real_exact_wrong.to_excel(writer, sheet_name="BothStrictExactWrong", index=False)

        qwen_only_defensible_real_exact.to_excel(writer, sheet_name="QwenOnlyDefExact", index=False)
        gemma_only_defensible_real_exact.to_excel(writer, sheet_name="GemmaOnlyDefExact", index=False)
        both_defensible_real_exact_correct.to_excel(writer, sheet_name="BothDefExactCorrect", index=False)
        both_defensible_real_exact_wrong.to_excel(writer, sheet_name="BothDefExactWrong", index=False)

        qwen_only_label_adjusted_exact.to_excel(writer, sheet_name="QwenOnlyLabelAdj", index=False)
        gemma_only_label_adjusted_exact.to_excel(writer, sheet_name="GemmaOnlyLabelAdj", index=False)

    print(f"Created: {OUTPUT_XLSX}")

    print("\n=== FIELD ACCURACY SUMMARY ===")
    print(summary_df.to_string(index=False))

    print("\n=== PREFERRED MODEL SUMMARY ===")
    print(preferred_summary.to_string(index=False))

    missing_qwen = (merged_df["qwen_audit_decision"] == "MISSING_AUDIT").sum()
    missing_gemma = (merged_df["gemma_audit_decision"] == "MISSING_AUDIT").sum()

    if missing_qwen or missing_gemma:
        print("\nWARNING: Some rows did not merge with audit decisions.")
        print(f"Missing Qwen audit rows: {missing_qwen}")
        print(f"Missing Gemma audit rows: {missing_gemma}")


if __name__ == "__main__":
    main()