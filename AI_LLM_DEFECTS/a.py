import pandas as pd
from sklearn.metrics import recall_score, classification_report

INPUT_XLSX = "accuracy_validation_100_rows.xlsx"
OUTPUT_XLSX = "component_error_analysis.xlsx"

# Ground truth columns
REAL_PRIMARY_COL = "Primary Component"
REAL_SECONDARY_COL = "Secondary Component code"
REAL_REASON_COL = "Failure Reason "

# Gemma / v2 prediction columns
PRED_PRIMARY_COL = "FirstComponentPred2"
PRED_SECONDARY_COL = "SecondaryComponentPred2"
PRED_REASON_COL = "FailureReasonPred2"


def clean_label(value):
    if pd.isna(value):
        return ""
    return str(value).strip()


def make_report_df(y_true, y_pred):
    report = classification_report(
        y_true,
        y_pred,
        zero_division=0,
        output_dict=True
    )

    df_report = pd.DataFrame(report).T.reset_index()
    df_report = df_report.rename(columns={"index": "Label"})

    return df_report


def make_error_summary(df, real_col, pred_col):
    wrong_df = df[df[real_col] != df[pred_col]].copy()

    summary = (
        wrong_df
        .groupby([real_col, pred_col])
        .size()
        .reset_index(name="ErrorCount")
        .sort_values("ErrorCount", ascending=False)
    )

    return summary


def make_label_weakness_summary(df, real_col, pred_col):
    rows = []

    labels = sorted(set(df[real_col].dropna().unique()))

    for label in labels:
        label_df = df[df[real_col] == label]
        total = len(label_df)

        correct = (label_df[real_col] == label_df[pred_col]).sum()
        wrong = total - correct

        recall = correct / total if total else 0

        most_common_wrong = (
            label_df[label_df[real_col] != label_df[pred_col]][pred_col]
            .value_counts()
            .head(3)
            .to_dict()
        )

        rows.append({
            "TrueLabel": label,
            "TotalRows": total,
            "Correct": correct,
            "Wrong": wrong,
            "Recall": round(recall, 4),
            "MostCommonWrongPredictions": str(most_common_wrong)
        })

    return (
        pd.DataFrame(rows)
        .sort_values(["Wrong", "Recall"], ascending=[False, True])
    )


def analyze_level(df, name, real_col, pred_col, writer):
    y_true = df[real_col].apply(clean_label)
    y_pred = df[pred_col].apply(clean_label)

    macro_recall = recall_score(
        y_true,
        y_pred,
        average="macro",
        zero_division=0
    )

    print(f"\n{name} Macro Recall: {macro_recall:.4f}")
    print(f"\nClassification Report - {name}")
    print(
        classification_report(
            y_true,
            y_pred,
            zero_division=0
        )
    )

    report_df = make_report_df(y_true, y_pred)
    error_summary = make_error_summary(df, real_col, pred_col)
    weakness_summary = make_label_weakness_summary(df, real_col, pred_col)

    report_df.to_excel(writer, sheet_name=f"{name}_report", index=False)
    error_summary.to_excel(writer, sheet_name=f"{name}_errors", index=False)
    weakness_summary.to_excel(writer, sheet_name=f"{name}_weakness", index=False)

    return {
        "Level": name,
        "MacroRecall": macro_recall,
        "TotalRows": len(df),
        "TotalWrong": int((y_true != y_pred).sum()),
        "Accuracy": round((y_true == y_pred).mean(), 4)
    }


def main():
    df = pd.read_excel(INPUT_XLSX)
    
    required_cols = [
        REAL_PRIMARY_COL,
        REAL_SECONDARY_COL,
        REAL_REASON_COL,
        PRED_PRIMARY_COL,
        PRED_SECONDARY_COL,
        PRED_REASON_COL,
    ]

    for col in required_cols:
        if col not in df.columns:
            raise ValueError(f"Missing required column: {col}")

    for col in required_cols:
        df[col] = df[col].apply(clean_label)

    with pd.ExcelWriter(OUTPUT_XLSX, engine="openpyxl") as writer:
        overall_rows = []

        overall_rows.append(
            analyze_level(
                df,
                "Primary",
                REAL_PRIMARY_COL,
                PRED_PRIMARY_COL,
                writer
            )
        )

        overall_rows.append(
            analyze_level(
                df,
                "Secondary",
                REAL_SECONDARY_COL,
                PRED_SECONDARY_COL,
                writer
            )
        )

        overall_rows.append(
            analyze_level(
                df,
                "Reason",
                REAL_REASON_COL,
                PRED_REASON_COL,
                writer
            )
        )

        overall_df = pd.DataFrame(overall_rows)
        overall_df.to_excel(writer, sheet_name="overall_summary", index=False)

        # Full wrong rows for manual review
        wrong_any = df[
            (df[REAL_PRIMARY_COL] != df[PRED_PRIMARY_COL])
            | (df[REAL_SECONDARY_COL] != df[PRED_SECONDARY_COL])
            | (df[REAL_REASON_COL] != df[PRED_REASON_COL])
        ].copy()

        wrong_any.to_excel(writer, sheet_name="all_wrong_rows", index=False)

    print(f"\nCreated: {OUTPUT_XLSX}")


if __name__ == "__main__":
    main()