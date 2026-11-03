import pandas as pd
import time
from classifierv2 import classify
from config import (
        PRIMARY_COMPONENTS,
        SECONDARY_COMPONENTS,
        FAILURE_REASONS
    )


INPUT_CSV = "WarrantyTrainningSet.csv"
OUTPUT_XLSX = "accuracy_validation_100_rows.xlsx"

SAMPLE_SIZE = 10


RANDOM_STATE = 42

# Ground truth columns
REAL_PRIMARY_COL = "Primary Component"
REAL_SECONDARY_COL = "Secondary Component code"
REAL_REASON_COL = "Failure Reason "

# Existing v1 prediction columns
CURRENT_PRIMARY_COL = "FirstComponentPred"
CURRENT_SECONDARY_COL = "SecondaryComponentPred"
CURRENT_REASON_COL = "FailureReasonPred"

SECONDARY_ALIASES = {
    "COND/EV": "Evaporator",
    "COND/EVAP-COILLEAK": "Cond/Evap - coil leak",
    "COND/EVAP-FANMOTOR": "Cond/Evap - Fan motor",
    "COND/EVAP-FANBLADES": "Cond/Evap - Fan blades",

    "INPUTDEVICES-THERMISTOR": "Input devices - Thermistor",
    "INPUTDEVICES-TRANSDUCER": "Input devices - Transducer",
    "INPUTDEVICES-TEMPSENSOR": "Input devices - Temp sensor",
    "INPUTDEVICES-FLOWSWITCH": "Input devices -Flow Switch",
    "INPUTDEVICES-HIGHPRESSURESWITCH": "Input devices - High pressure switch",
    "INPUTDEVICES-SENSOR": "Input devices - Sensor",

    "NC-OTHER(COMMENTSBOX)": "NC - Other (comments box)",
    "NC-CONCESSION": "NC - concession",
    "NC-NOWARRANTY": "NC - Not Warranty",
    "NC-FIELDINSTALLISSUE": "NC - field install issue",
    "NC-FRAME": "NC - frame",
    "NC-REFRIGERANTLEAK": "NC - Refrigerant Leak",
    "NC-WATERLEAK": "NC - Water Leak",
    "NC-COSMETIC": "NC - Cosmetic",
    "NC-REFRIGERANTOVERCHARGE": "NC - refrigerant overcharge",
    "NC-REFRIGERANTUNDERCHARGE": "NC - refrigerant undercharge",
    "NC-CONFIGURATION": "NC - configuration",
    "NC-NOFAULTFOUND": "NC - no fault found",
    "NC-SYSTEMCONTAMINATION": "NC - system contamination",
    "NC-SERVICECALL": "NC - service call",
    "NC-MISSINGPART": "NC - missing parts",
    "NC-INSULATION": "NC - insulation",
    "NC-SALESORDERISSUE": "NC - sales order issue",

    "VALVE-ECONOMIZER": "Valve - economizer",
    "VALVE-BALL": "Valve - Ball",
    "VALVE-EXV/TXV": "Valve - EXV/TXV",
    "VALVE-CHARGING/SERVICE": "Valve - charging/service",
    "VALVE-ACTUATOR": "Valve - actuator",
    "VALVE-DAMPER": "Valve - damper",
    "VALVE-CHECK": "Valve - Check",
    "VALVE-STEPPER": "Valve - Stepper",

    "COMPRESSOR-WIRING": "Compressor - wiring",
    "COMPRESSOR-MOTOR": "Compressor - Motor",
    "COMPRESSOR-HEATER": "Compressor - Heater",
    "COMPRESSOR-MECHANICAL": "Compressor - Mechanical failure",

    "ELECTRICALCONTROLS-WIRING": "Electrical Controls - Wiring",
    "ELECTRICALCONTROLS-BOARD": "Electrical Controls - Boards",
    "ELECTRICALCONTROLS-BREAKER": "Electrical Controls - Breakers",
    "ELECTRICALCONTROLS-CONTACTOR": "Electrical Controls - Contactors",
    "ELECTRICALCONTROLS-PROGRAM": "Electrical Controls - Program",
    "ELECTRICALCONTROLS-FUSES": "Electrical Controls - fuses",
    "ELECTRICALCONTROLS-RELAYS": "Electrical Controls - Relays",
    "ELECTRICALCONTROLS-DISPLAY": "Electrical controls - display",
    "ELECTRICALCONTROLS-TRANSFORMER": "Electrical Controls - Transformer",

    "ELECTRONICCONTROLS-WIRING": "Electronic Controls - wiring",
    "ELECTRONICCONTROLS-PROGRAM": "Electronic controls - program",

    "STARTER/VFD-BOARD": "Starter/VFD - Boards",
    "STARTER/VFD-WIRING": "Starter/VFD - wiring",
    "STARTER/VFD-PROGRAM": "Starter/VFD - Program",

    "GAS-INDUCER": "Gas - Inducer",
    "GAS-HX": "Gas - HX",
    "GAS-SENSOR": "Gas - Sensor",
    "GAS-BURNER": "Gas-burner",
    "GAS-LEAK": "Gas - leak",
    "GAS-VALVE": "Gas - Valve",
    "GAS-EXHAUST": "Gas - exhaust",

    "OILSYSTEM-OILLINE": "Oil system - oil line",
}
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
    )


def normalize_to_taxonomy(value, taxonomy_list):
    if pd.isna(value):
        return ""

    key = normalize_key(value)

    if taxonomy_list == SECONDARY_COMPONENTS and key in SECONDARY_ALIASES:
        return SECONDARY_ALIASES[key]

    cleaned = (
        str(value)
        .strip()
        .lower()
        .replace("/", "")
        .replace("-", "")
        .replace("_", "")
        .replace(" ", "")
    )

    for item in taxonomy_list:
        normalized_item = (
            item.strip()
            .lower()
            .replace("/", "")
            .replace("-", "")
            .replace("_", "")
            .replace(" ", "")
        )

        if cleaned == normalized_item:
            return item

    return value

def main():
    overall_start = time.perf_counter()
    df = pd.read_csv(INPUT_CSV)


    df[REAL_PRIMARY_COL] = df[REAL_PRIMARY_COL].apply(
        lambda x: normalize_to_taxonomy(x, PRIMARY_COMPONENTS)
    )

    df[REAL_SECONDARY_COL] = df[REAL_SECONDARY_COL].apply(
        lambda x: normalize_to_taxonomy(x, SECONDARY_COMPONENTS)
    )

    df[REAL_REASON_COL] = df[REAL_REASON_COL].apply(
        lambda x: normalize_to_taxonomy(x, FAILURE_REASONS)
    )

    df[CURRENT_PRIMARY_COL] = df[CURRENT_PRIMARY_COL].apply(
        lambda x: normalize_to_taxonomy(x, PRIMARY_COMPONENTS)
    )

    df[CURRENT_SECONDARY_COL] = df[CURRENT_SECONDARY_COL].apply(
        lambda x: normalize_to_taxonomy(x, SECONDARY_COMPONENTS)
    )

    df[CURRENT_REASON_COL] = df[CURRENT_REASON_COL].apply(
        lambda x: normalize_to_taxonomy(x, FAILURE_REASONS)
    )

    required_cols = [
        "ServicePerformed",

        REAL_PRIMARY_COL,
        REAL_SECONDARY_COL,
        REAL_REASON_COL,

        CURRENT_PRIMARY_COL,
        CURRENT_SECONDARY_COL,
        CURRENT_REASON_COL,
    ]

    for col in required_cols:
        if col not in df.columns:
            raise ValueError(f"Missing required column: {col}")

    df = df[
        df["ServicePerformed"].notna()
        & (df["ServicePerformed"].astype(str).str.strip() != "")
    ].copy()

    # Random benchmark sample
    sample_df = df.sample(
        n=min(SAMPLE_SIZE, len(df)),
        random_state=RANDOM_STATE
    ).copy()

    print(f"Rows selected for benchmark: {len(sample_df)}")

    # New AI prediction columns
    sample_df["FirstComponentPred2"] = ""
    sample_df["SecondaryComponentPred2"] = ""
    sample_df["FailureReasonPred2"] = ""

    sample_df["ConfidencePred2"] = 0.0
    sample_df["EvidencePred2"] = ""
    sample_df["ReasoningSummaryPred2"] = ""

    # Run AI predictions
    for idx, row in sample_df.iterrows():

        print(f"[{idx+1}/{len(sample_df)}] Running benchmark")

        service_text = clean_text(row["ServicePerformed"])
        replacement_part = str(
            row.get("ReplacementPartDescription", "")
        ).strip()

        if not replacement_part:
            replacement_part = "Not Provided"
        result = classify(text=service_text, replacement_part_description=replacement_part, model="gemma3:12B")

        if result.get("confidence", 0) == 0 and "empty response" in result.get("reasoning_summary", "").lower():
            result = classify(text=service_text, model="llama3")

        sample_df.at[idx, "FirstComponentPred2"] = result.get(
            "primary_component", ""
        )

        sample_df.at[idx, "SecondaryComponentPred2"] = result.get(
            "secondary_component", ""
        )

        sample_df.at[idx, "FailureReasonPred2"] = result.get(
            "failure_reason", ""
        )

        sample_df.at[idx, "ConfidencePred2"] = float(
            result.get("confidence", 0.0) or 0.0
        )

        sample_df.at[idx, "EvidencePred2"] = "; ".join(
            result.get("evidence_phrases", [])
        )

        sample_df.at[idx, "ReasoningSummaryPred2"] = result.get(
            "reasoning_summary", ""
        )

    # Compare AI vs Ground Truth
    sample_df["PrimaryMatch_v2"] = (
    sample_df["FirstComponentPred2"].apply(normalize_key)
    ==
    sample_df[REAL_PRIMARY_COL].apply(normalize_key)
    )

    sample_df["SecondaryMatch_v2"] = (
        sample_df["SecondaryComponentPred2"].apply(normalize_key)
        ==
        sample_df[REAL_SECONDARY_COL].apply(normalize_key)
    )

    sample_df["ReasonMatch_v2"] = (
        sample_df["FailureReasonPred2"].apply(normalize_key)
        ==
        sample_df[REAL_REASON_COL].apply(normalize_key)
    )
    # Compare Existing Model vs Ground Truth
    sample_df["PrimaryMatch_v1"] = (
        sample_df[CURRENT_PRIMARY_COL]
        == sample_df[REAL_PRIMARY_COL]
    )

    sample_df["SecondaryMatch_v1"] = (
        sample_df[CURRENT_SECONDARY_COL]
        == sample_df[REAL_SECONDARY_COL]
    )

    sample_df["ReasonMatch_v1"] = (
        sample_df[CURRENT_REASON_COL]
        == sample_df[REAL_REASON_COL]
    )

    # Accuracy metrics
    primary_v1 = round(sample_df["PrimaryMatch_v1"].mean() * 100, 2)
    secondary_v1 = round(sample_df["SecondaryMatch_v1"].mean() * 100, 2)
    reason_v1 = round(sample_df["ReasonMatch_v1"].mean() * 100, 2)

    primary_v2 = round(sample_df["PrimaryMatch_v2"].mean() * 100, 2)
    secondary_v2 = round(sample_df["SecondaryMatch_v2"].mean() * 100, 2)
    reason_v2 = round(sample_df["ReasonMatch_v2"].mean() * 100, 2)

    print("\n=== ACCURACY RESULTS ===")

    print("\nCURRENT MODEL (v1)")
    print("Primary Accuracy:", primary_v1, "%")
    print("Secondary Accuracy:", secondary_v1, "%")
    print("Failure Reason Accuracy:", reason_v1, "%")

    print("\nLLAMA3 MODEL (v2)")
    print("Primary Accuracy:", primary_v2, "%")
    print("Secondary Accuracy:", secondary_v2, "%")
    print("Failure Reason Accuracy:", reason_v2, "%")

    overall_elapsed = (time.perf_counter() - overall_start)/60

    print(f"\nTotal runtime: {overall_elapsed:.2f} minutes")
    print(f"Average per row: {overall_elapsed / len(sample_df):.2f} minutes")

    # Export
    with pd.ExcelWriter(
        OUTPUT_XLSX,
        engine="openpyxl"
    ) as writer:

        sample_df.to_excel(
            writer,
            sheet_name="Benchmark_Results",
            index=False
        )

    print(f"\nExcel created: {OUTPUT_XLSX}")


if __name__ == "__main__":
    main()