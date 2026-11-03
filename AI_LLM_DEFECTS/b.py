import pandas as pd

INPUT_XLSX = "accuracy_validation_100_rows.xlsx"
OUTPUT_XLSX = "two_of_three_wrong_analysis.xlsx"

MATCH_COLS = [
    "PrimaryMatch_v2",
    "SecondaryMatch_v2",
    "ReasonMatch_v2",
]

REAL_PRIMARY_COL = "Primary Component"
REAL_SECONDARY_COL = "Secondary Component code"
REAL_REASON_COL = "Failure Reason "

PRED_PRIMARY_COL = "FirstComponentPred2"
PRED_SECONDARY_COL = "SecondaryComponentPred2"
PRED_REASON_COL = "FailureReasonPred2"


def explain_error_pattern(row):
    wrong = []

    if not row["PrimaryMatch_v2"]:
        wrong.append("Primary")
    if not row["SecondaryMatch_v2"]:
        wrong.append("Secondary")
    if not row["ReasonMatch_v2"]:
        wrong.append("Failure Reason")

    return " + ".join(wrong)


def main():
    df = pd.read_excel(INPUT_XLSX)

    for col in MATCH_COLS:
        if col not in df.columns:
            raise ValueError(f"Missing required column: {col}")

    df["CorrectCount"] = df[MATCH_COLS].sum(axis=1)
    df["WrongCount"] = 3 - df["CorrectCount"]

    focus_df = df[df["WrongCount"] == 2].copy()

    focus_df["ErrorPattern"] = focus_df.apply(explain_error_pattern, axis=1)

    selected_cols = [
        "ServicePerformed",

        REAL_PRIMARY_COL,
        PRED_PRIMARY_COL,
        "PrimaryMatch_v2",

        REAL_SECONDARY_COL,
        PRED_SECONDARY_COL,
        "SecondaryMatch_v2",

        REAL_REASON_COL,
        PRED_REASON_COL,
        "ReasonMatch_v2",

        "ErrorPattern",
    ]

    focus_df = focus_df[selected_cols]

    summary = (
        focus_df["ErrorPattern"]
        .value_counts()
        .reset_index()
    )
    summary.columns = ["ErrorPattern", "Count"]

    pair_summary = (
        focus_df.groupby([
            REAL_PRIMARY_COL,
            PRED_PRIMARY_COL,
            REAL_SECONDARY_COL,
            PRED_SECONDARY_COL,
            REAL_REASON_COL,
            PRED_REASON_COL,
        ])
        .size()
        .reset_index(name="Count")
        .sort_values("Count", ascending=False)
    )

    with pd.ExcelWriter(OUTPUT_XLSX, engine="openpyxl") as writer:
        focus_df.to_excel(writer, sheet_name="2_of_3_wrong_rows", index=False)
        summary.to_excel(writer, sheet_name="error_pattern_summary", index=False)
        pair_summary.to_excel(writer, sheet_name="label_pair_summary", index=False)

    print("Rows with exactly 2 wrong:", len(focus_df))
    print("\nError pattern summary:")
    print(summary)

    print(f"\nCreated: {OUTPUT_XLSX}")


if __name__ == "__main__":
    main()