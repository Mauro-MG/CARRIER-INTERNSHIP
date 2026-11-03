import pandas as pd
import time
from classifierv3 import classify

INPUT_CSV = "WarrantyTrainningSet.csv"
OUTPUT_XLSX = "targeted_original_rows_test.xlsx"

MODEL = "gemma4:12b"

# Put the original CSV row indexes you want to test here
TARGET_ROWS = [
    10,
    25,
    87,
    176,
]

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


def main():
    df = pd.read_csv(INPUT_CSV)

    targeted_df = df.loc[TARGET_ROWS].copy()

    results = []

    for idx, row in targeted_df.iterrows():
        service_text = clean(row.get(SERVICE_COL, ""))
        replacement_part = clean(row.get(PART_COL, "")) or "Not Provided"

        print("\n" + "=" * 100)
        print(f"CSV Index: {idx}")
        print("ServicePerformed:")
        print(service_text)
        print("\nReplacementPartDescription:")
        print(replacement_part)

        start = time.perf_counter()

        result = classify(
            text=service_text,
            replacement_part_description=replacement_part,
            model=MODEL
        )

        elapsed = time.perf_counter() - start

        real_primary = clean(row.get(REAL_PRIMARY_COL, ""))
        real_secondary = clean(row.get(REAL_SECONDARY_COL, ""))
        real_reason = clean(row.get(REAL_REASON_COL, ""))

        pred_primary = result.get("primary_component", "")
        pred_secondary = result.get("secondary_component", "")
        pred_reason = result.get("failure_reason", "")

        print("\nREAL:")
        print(real_primary, "|", real_secondary, "|", real_reason)

        print("\nPRED:")
        print(pred_primary, "|", pred_secondary, "|", pred_reason)

        results.append({
            "CSVIndex": idx,
            "ServicePerformed": service_text,
            "ReplacementPartDescription": replacement_part,

            "RealPrimary": real_primary,
            "PredPrimary": pred_primary,
            "PrimaryMatch": normalize_key(real_primary) == normalize_key(pred_primary),

            "RealSecondary": real_secondary,
            "PredSecondary": pred_secondary,
            "SecondaryMatch": normalize_key(real_secondary) == normalize_key(pred_secondary),

            "RealReason": real_reason,
            "PredReason": pred_reason,
            "ReasonMatch": normalize_key(real_reason) == normalize_key(pred_reason),

            "ModelUsed": result.get("model_used", MODEL),
            "Confidence": result.get("confidence", ""),
            "ReasoningSummary": result.get("reasoning_summary", ""),
            "RawResponse": result.get("raw_response", ""),
            "ProcessingTimeSec": round(elapsed, 2),
        })

    out_df = pd.DataFrame(results)
    out_df.to_excel(OUTPUT_XLSX, index=False)

    print(f"\nCreated: {OUTPUT_XLSX}")


if __name__ == "__main__":
    main()