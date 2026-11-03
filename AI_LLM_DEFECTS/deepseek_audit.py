import pandas as pd
import json
import time
import ollama

INPUT_XLSX = "accuracy_validation_100_rows.xlsx"
INPUT_SHEET = "Benchmark_Results"
OUTPUT_XLSX = "deepseek_audit_results.xlsx"

MODEL = "deepseek-r1:8b"

AUDIT_MODE = "all_wrong"  
# options:
# "all_wrong" = audit rows with 1+ mistakes
# "major_only" = audit rows with 2+ mistakes
# "one_only" = audit rows with exactly 1 mistake

SERVICE_COL = "ServicePerformed"
PART_COL = "ReplacementPartDescription"

REAL_PRIMARY_COL = "Primary Component"
REAL_SECONDARY_COL = "Secondary Component code"
REAL_REASON_COL = "Failure Reason "

PRED_PRIMARY_COL = "FirstComponentPred2"
PRED_SECONDARY_COL = "SecondaryComponentPred2"
PRED_REASON_COL = "FailureReasonPred2"

VALID_DECISIONS = {
    "MODEL_CORRECT",
    "LABEL_QUESTIONABLE",
    "BOTH_DEFENSIBLE",
    "MODEL_WRONG",
}


def clean(value):
    if pd.isna(value):
        return ""
    return str(value).strip()


def extract_decision(raw):
    raw = clean(raw).upper()

    if "</THINK>" in raw:
        raw = raw.split("</THINK>")[-1].strip()

    for decision in VALID_DECISIONS:
        if decision in raw:
            return decision

    try:
        data = json.loads(raw)
        decision = str(data.get("decision", "")).upper().strip()
        if decision in VALID_DECISIONS:
            return decision
    except Exception:
        pass

    return "MODEL_WRONG"


def call_model(prompt):
    response = ollama.generate(
        model=MODEL,
        prompt=prompt,
        options={
            "temperature": 0.0,
            "top_p": 0.1,
            "num_ctx": 8192,
            "num_predict": 400,
        },
        keep_alive="30m",
    )
    return response.get("response", "").strip()


def build_prompt(row):
    return f"""
You are auditing HVAC warranty classification disagreements.

Return ONLY one exact option:
MODEL_CORRECT
LABEL_QUESTIONABLE
BOTH_DEFENSIBLE
MODEL_WRONG

Definitions:
MODEL_CORRECT = model prediction is clearly more reasonable than the training label.
LABEL_QUESTIONABLE = training label is weak, unsupported, inconsistent, or likely wrong.
BOTH_DEFENSIBLE = both are reasonable because of taxonomy overlap or limited evidence.
MODEL_WRONG = training label is clearly better and model prediction is clearly incorrect.

SERVICE PERFORMED:
{clean(row.get(SERVICE_COL, ""))}

REPLACEMENT PART DESCRIPTION:
{clean(row.get(PART_COL, "")) or "Not Provided"}

TRAINING LABEL:
primary_component = {clean(row.get(REAL_PRIMARY_COL, ""))}
secondary_component = {clean(row.get(REAL_SECONDARY_COL, ""))}
failure_reason = {clean(row.get(REAL_REASON_COL, ""))}

MODEL PREDICTION:
primary_component = {clean(row.get(PRED_PRIMARY_COL, ""))}
secondary_component = {clean(row.get(PRED_SECONDARY_COL, ""))}
failure_reason = {clean(row.get(PRED_REASON_COL, ""))}

Return only the decision.
"""


def main():
    start = time.perf_counter()

    df = pd.read_excel(INPUT_XLSX, sheet_name=INPUT_SHEET)

    df["DisagreementCount"] = (
        (~df["PrimaryMatch_v2"]).astype(int)
        + (~df["SecondaryMatch_v2"]).astype(int)
        + (~df["ReasonMatch_v2"]).astype(int)
    )

    if AUDIT_MODE == "major_only":
        audit_df = df[df["DisagreementCount"] >= 2].copy()
    elif AUDIT_MODE == "one_only":
        audit_df = df[df["DisagreementCount"] == 1].copy()
    else:
        audit_df = df[df["DisagreementCount"] >= 1].copy()

    print("\nDisagreement distribution:")
    print(df["DisagreementCount"].value_counts().sort_index())
    print(f"\nRows sent to DeepSeek: {len(audit_df)}")

    audit_df["ModelAuditDecision"] = ""
    audit_df["ModelAuditRaw"] = ""
    audit_df["ModelAuditUsed"] = MODEL

    for counter, (idx, row) in enumerate(audit_df.iterrows(), start=1):
        print(f"[{counter}/{len(audit_df)}] Reviewing index {idx}")

        raw = call_model(build_prompt(row))
        decision = extract_decision(raw)

        audit_df.at[idx, "ModelAuditDecision"] = decision
        audit_df.at[idx, "ModelAuditRaw"] = raw

        print("Decision:", decision)

    summary = audit_df["ModelAuditDecision"].value_counts().reset_index()
    summary.columns = ["ModelAuditDecision", "Count"]
    summary["Percent"] = summary["Count"] / len(audit_df)

    with pd.ExcelWriter(OUTPUT_XLSX, engine="openpyxl") as writer:
        summary.to_excel(writer, sheet_name="Summary", index=False)
        audit_df.to_excel(writer, sheet_name="AuditReviewed", index=False)

    print(f"\nCreated: {OUTPUT_XLSX}")
    print(f"Runtime: {(time.perf_counter() - start) / 60:.2f} minutes")
    print(summary.to_string(index=False))


if __name__ == "__main__":
    main()