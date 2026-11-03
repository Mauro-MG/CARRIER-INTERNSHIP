import pandas as pd
import re

INPUT_XLSX = "accuracy_validation_100_rows.xlsx"
OUTPUT_XLSX = "reverse_engineering_grouped_errors.xlsx"

REAL_PRIMARY_COL = "Primary Component"
REAL_SECONDARY_COL = "Secondary Component code"
REAL_REASON_COL = "Failure Reason "

PRED_PRIMARY_COL = "FirstComponentPred2"
PRED_SECONDARY_COL = "SecondaryComponentPred2"
PRED_REASON_COL = "FailureReasonPred2"

SERVICE_COL = "ServicePerformed"
PART_COL = "ReplacementPartDescription"


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


def safe_sheet_name(name):
    return re.sub(r"[\[\]\:\*\?\/\\]", "_", str(name))[:31]


def select_cols(df):
    cols = [
        SERVICE_COL,
        PART_COL,

        REAL_PRIMARY_COL,
        PRED_PRIMARY_COL,
        "PrimaryMatch",

        REAL_SECONDARY_COL,
        PRED_SECONDARY_COL,
        "SecondaryMatch",

        REAL_REASON_COL,
        PRED_REASON_COL,
        "ReasonMatch",

        "CorrectCount",
        "WrongCount",
    ]
    return df[[c for c in cols if c in df.columns]].copy()


def main():
    df = pd.read_excel(INPUT_XLSX, sheet_name="Benchmark_Results")

    df["PrimaryMatch"] = (
        df[REAL_PRIMARY_COL].apply(normalize_key)
        == df[PRED_PRIMARY_COL].apply(normalize_key)
    )

    df["SecondaryMatch"] = (
        df[REAL_SECONDARY_COL].apply(normalize_key)
        == df[PRED_SECONDARY_COL].apply(normalize_key)
    )

    df["ReasonMatch"] = (
        df[REAL_REASON_COL].apply(normalize_key)
        == df[PRED_REASON_COL].apply(normalize_key)
    )

    df["CorrectCount"] = (
        df["PrimaryMatch"].astype(int)
        + df["SecondaryMatch"].astype(int)
        + df["ReasonMatch"].astype(int)
    )

    df["WrongCount"] = 3 - df["CorrectCount"]

    primary_confusions = (
        df[df["PrimaryMatch"] == False]
        .groupby([REAL_PRIMARY_COL, PRED_PRIMARY_COL])
        .size()
        .reset_index(name="Count")
        .sort_values("Count", ascending=False)
    )

    secondary_confusions = (
        df[df["SecondaryMatch"] == False]
        .groupby([REAL_SECONDARY_COL, PRED_SECONDARY_COL])
        .size()
        .reset_index(name="Count")
        .sort_values("Count", ascending=False)
    )

    reason_confusions = (
        df[df["ReasonMatch"] == False]
        .groupby([REAL_REASON_COL, PRED_REASON_COL])
        .size()
        .reset_index(name="Count")
        .sort_values("Count", ascending=False)
    )

    summary = pd.DataFrame([
        {"Metric": "Total rows", "Value": len(df)},
        {"Metric": "Primary wrong", "Value": int((df["PrimaryMatch"] == False).sum())},
        {"Metric": "Secondary wrong", "Value": int((df["SecondaryMatch"] == False).sum())},
        {"Metric": "Reason wrong", "Value": int((df["ReasonMatch"] == False).sum())},
        {"Metric": "Two or more wrong", "Value": int((df["WrongCount"] >= 2).sum())},
        {"Metric": "All three wrong", "Value": int((df["WrongCount"] == 3).sum())},
    ])

    with pd.ExcelWriter(OUTPUT_XLSX, engine="openpyxl") as writer:
        summary.to_excel(writer, sheet_name="Summary", index=False)

        primary_confusions.to_excel(writer, sheet_name="PrimaryConfusions", index=False)
        secondary_confusions.to_excel(writer, sheet_name="SecondaryConfusions", index=False)
        reason_confusions.to_excel(writer, sheet_name="ReasonConfusions", index=False)

        select_cols(df[df["PrimaryMatch"] == False]).to_excel(
            writer, sheet_name="PrimaryWrong", index=False
        )

        select_cols(df[df["SecondaryMatch"] == False]).to_excel(
            writer, sheet_name="SecondaryWrong", index=False
        )

        select_cols(df[df["ReasonMatch"] == False]).to_excel(
            writer, sheet_name="ReasonWrong", index=False
        )

        select_cols(df[df["WrongCount"] >= 2]).to_excel(
            writer, sheet_name="TwoOrMoreWrong", index=False
        )

        # Top confusion pair sheets
        used_names = set()

        for _, row in primary_confusions.head(10).iterrows():
            real = row[REAL_PRIMARY_COL]
            pred = row[PRED_PRIMARY_COL]

            subset = df[
                (df[REAL_PRIMARY_COL] == real)
                & (df[PRED_PRIMARY_COL] == pred)
            ]

            sheet = safe_sheet_name(f"P_{real[:10]}_to_{pred[:10]}")
            while sheet in used_names:
                sheet = safe_sheet_name(sheet[:28] + "_x")
            used_names.add(sheet)

            select_cols(subset).to_excel(writer, sheet_name=sheet, index=False)

        for _, row in secondary_confusions.head(10).iterrows():
            real = row[REAL_SECONDARY_COL]
            pred = row[PRED_SECONDARY_COL]

            subset = df[
                (df[REAL_SECONDARY_COL] == real)
                & (df[PRED_SECONDARY_COL] == pred)
            ]

            sheet = safe_sheet_name(f"S_{real[:10]}_to_{pred[:10]}")
            while sheet in used_names:
                sheet = safe_sheet_name(sheet[:28] + "_x")
            used_names.add(sheet)

            select_cols(subset).to_excel(writer, sheet_name=sheet, index=False)

        for _, row in reason_confusions.head(10).iterrows():
            real = row[REAL_REASON_COL]
            pred = row[PRED_REASON_COL]

            subset = df[
                (df[REAL_REASON_COL] == real)
                & (df[PRED_REASON_COL] == pred)
            ]

            sheet = safe_sheet_name(f"R_{real[:10]}_to_{pred[:10]}")
            while sheet in used_names:
                sheet = safe_sheet_name(sheet[:28] + "_x")
            used_names.add(sheet)

            select_cols(subset).to_excel(writer, sheet_name=sheet, index=False)

    print(f"Created: {OUTPUT_XLSX}")
    print("\nPrimary Confusions:")
    print(primary_confusions.head(15).to_string(index=False))

    print("\nSecondary Confusions:")
    print(secondary_confusions.head(15).to_string(index=False))

    print("\nReason Confusions:")
    print(reason_confusions.head(15).to_string(index=False))


if __name__ == "__main__":
    main()