import os
import json
from datetime import datetime
import pandas as pd
from flask import Flask, render_template, request, redirect, url_for, send_file, flash
from datetime import datetime
from collections import defaultdict
from db import load_claims, test_sql_connection, load_last_week_claims_with_serial_history
from classifier import classify
from config import PRIMARY_COMPONENTS, SECONDARY_COMPONENTS, FAILURE_REASONS, VALID_SECONDARY_BY_PRIMARY

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "")

CLAIMS_CACHE = []
RESULTS_CACHE = []
OUTPUT_PATH = os.path.join("outputs", "classified_claims.csv")


def parse_date_safe(value):
    if not value:
        return None

    try:
        return datetime.strptime(str(value)[:10], "%Y-%m-%d")
    except Exception:
        return None

def build_serial_context(claim, all_claims):
    serial = claim.get("Serial", "")

    serial_claims = [
        row for row in all_claims
        if row.get("Serial") == serial
    ]

    serial_claims = sorted(
        serial_claims,
        key=lambda x: x.get("DateFailed", "")
    )

    context_parts = []

    for row in serial_claims:
        context_parts.append(
            f"""
ClaimNumber: {row.get("ClaimNumber", "")}
DateFailed: {row.get("DateFailed", "")}
PaidDate: {row.get("PaidDate", "")}
ClaimType: {row.get("ClaimType", "")}
WarrantyType: {row.get("WarrantyType", "")}
TimeType: {row.get("TimeType", "")}
ServicePerformed:
{row.get("ServicePerformed", "")}
"""
        )

    return "\n--- HISTORICAL CLAIM ---\n".join(context_parts)

def group_results_by_serial_and_1_months(results):
    grouped = defaultdict(list)

    for row in results:
        serial = row.get("Serial", "Unknown Serial")
        grouped[serial].append(row)

    final_groups = []

    for serial, rows in grouped.items():
        rows = sorted(
            rows,
            key=lambda x: parse_date_safe(x.get("DateFailed")) or datetime.min
        )

        current_group = []
        previous_date = None
        group_number = 1

        for row in rows:
            current_date = parse_date_safe(row.get("DateFailed"))

            if not current_group:
                current_group.append(row)
                previous_date = current_date
                continue

            if previous_date and current_date:
                days_apart = abs((current_date - previous_date).days)
            else:
                days_apart = 9999

            if days_apart <= 30:
                current_group.append(row)
            else:
                final_groups.append({
                    "serial": serial,
                    "group_number": group_number,
                    "claims": current_group
                })

                group_number += 1
                current_group = [row]

            previous_date = current_date

        if current_group:
            final_groups.append({
                "serial": serial,
                "group_number": group_number,
                "claims": current_group
            })

    return final_groups

def row_id(i):
    return str(i)

@app.route("/")
def dashboard():
    return render_template(
        "dashboard.html",
        claims=CLAIMS_CACHE,
        results=RESULTS_CACHE
    )
@app.route("/load", methods=["POST"])
def load():
    global CLAIMS_CACHE, RESULTS_CACHE

    try:
        limit = request.form.get("limit", "50")
        claim_number = request.form.get("claim_number", "").strip()
        serial = request.form.get("serial", "").strip()
        date_from = request.form.get("date_from", "").strip()
        date_to = request.form.get("date_to", "").strip()

        df = load_claims(
            limit=int(limit),
            claim_number=claim_number if claim_number else None,
            serial=serial if serial else None,
            date_from=date_from if date_from else None,
            date_to=date_to if date_to else None
        )

        df = df.fillna("")

        CLAIMS_CACHE = df.to_dict(orient="records")
        RESULTS_CACHE = []

        flash(f"Loaded {len(CLAIMS_CACHE)} claims.", "success")

    except Exception as e:
        flash(f"Error loading claims: {e}", "danger")

    return redirect(url_for("dashboard"))

@app.route("/load-last-week-history", methods=["POST"])
def load_last_week_history():
    global CLAIMS_CACHE, RESULTS_CACHE

    try:
        df = load_last_week_claims_with_serial_history()

        CLAIMS_CACHE = df.to_dict(orient="records")
        RESULTS_CACHE = []

        target_count = len([
            row for row in CLAIMS_CACHE
            if str(row.get("IsLastWeekTarget", "")) in ["1", "True", "true"]
        ])

        flash(
            f"Loaded {len(CLAIMS_CACHE)} historical rows for {target_count} last-week target claims.",
            "success"
        )

    except Exception as e:
        flash(f"Error loading last-week claims with history: {e}", "danger")

    return redirect(url_for("dashboard"))

@app.route("/review")
def review():
    global RESULTS_CACHE

    grouped_results = group_results_by_serial_and_1_months(RESULTS_CACHE)

    return render_template(
        "review.html",
        grouped_results=grouped_results,
        primary_components=PRIMARY_COMPONENTS,
        secondary_components=SECONDARY_COMPONENTS,
        failure_reasons=FAILURE_REASONS
    )




@app.route("/classify", methods=["POST"])
def classify_selected():
    global CLAIMS_CACHE, RESULTS_CACHE

    selected_indexes = request.form.getlist("selected_claims")

    if not CLAIMS_CACHE:
        flash("No claims are loaded. Load claims first.", "warning")
        return redirect(url_for("dashboard"))

    if not selected_indexes:
        flash("No claims selected.", "warning")
        return redirect(url_for("dashboard"))

    claims_to_classify = []

    for idx in selected_indexes:
        i = int(idx)

        if i < 0 or i >= len(CLAIMS_CACHE):
            continue

        selected_claim = CLAIMS_CACHE[i]
        selected_serial = selected_claim.get("Serial")
        selected_date = parse_date_safe(selected_claim.get("DateFailed"))

        if not selected_serial:
            claims_to_classify.append(selected_claim)
            continue

        for claim in CLAIMS_CACHE:
            claim_serial = claim.get("Serial")
            claim_date = parse_date_safe(claim.get("DateFailed"))

            if claim_serial != selected_serial:
                continue

            if selected_date and claim_date:
                days_apart = abs((claim_date - selected_date).days)

                if days_apart <= 30:
                    claims_to_classify.append(claim)
            else:
                claims_to_classify.append(claim)

    # Remove duplicates
    unique_claims = {}
    for claim in claims_to_classify:
        key = f"{claim.get('Serial', '')}_{claim.get('ClaimNumber', '')}_{claim.get('DateFailed', '')}"
        unique_claims[key] = claim

    claims_to_classify = list(unique_claims.values())

    for claim in claims_to_classify:
        if str(claim.get("IsLastWeekTarget", "")) not in ["1", "True", "true"]:
            continue

        text = claim.get("ServicePerformed", "")
        historical_context = build_serial_context(claim, CLAIMS_CACHE)

        ai_result = classify(
            text=text,
            historical_context=historical_context
        )

        result = {
            **claim,
            "AI_PrimaryComponent": ai_result.get("primary_component", ""),
            "AI_SecondaryComponent": ai_result.get("secondary_component", ""),
            "AI_FailureReason": ai_result.get("failure_reason", ""),
            "AI_Confidence": ai_result.get("confidence", ""),
            "AI_EvidencePhrases": "; ".join(ai_result.get("evidence_phrases", [])),
            "Final_PrimaryComponent": ai_result.get("primary_component", ""),
            "Final_SecondaryComponent": ai_result.get("secondary_component", ""),
            "Final_FailureReason": ai_result.get("failure_reason", ""),
            "Reviewed": "No"
        }

        RESULTS_CACHE.append(result)

    flash(f"Classified {len(claims_to_classify)} claims associated with selected Serial(s).", "success")

    return redirect(url_for("review"))


@app.route("/results")
def results():
    return render_template(
        "results.html",
        results=RESULTS_CACHE,
        primary_components=PRIMARY_COMPONENTS,
        secondary_components=SECONDARY_COMPONENTS,
        failure_reasons=FAILURE_REASONS,
        valid_secondary_by_primary=VALID_SECONDARY_BY_PRIMARY
    )



@app.route("/save", methods=["POST"])
def save_results():
    global RESULTS_CACHE

    for i, row in enumerate(RESULTS_CACHE):
        row["Final_PrimaryComponent"] = request.form.get(f"primary_{i}", row["Final_PrimaryComponent"])
        row["Final_SecondaryComponent"] = request.form.get(f"secondary_{i}", row["Final_SecondaryComponent"])
        row["Final_FailureReason"] = request.form.get(f"reason_{i}", row["Final_FailureReason"])
        row["Reviewed"] = "Yes"
        row["ReviewedAt"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    os.makedirs("outputs", exist_ok=True)
    pd.DataFrame(RESULTS_CACHE).to_csv(OUTPUT_PATH, index=False)
    flash("Saved reviewed results to CSV.")
    return redirect(url_for("results"))


@app.route("/download")
def download():
    if not os.path.exists(OUTPUT_PATH):
        pd.DataFrame(RESULTS_CACHE).to_csv(OUTPUT_PATH, index=False)
    return send_file(OUTPUT_PATH, as_attachment=True)


if __name__ == "__main__":
    app.run(debug=True)
