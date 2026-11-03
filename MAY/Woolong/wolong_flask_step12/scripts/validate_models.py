from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Allow running from project root or scripts/.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from services.validation import validate_csv_file, write_validation_report_csv


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate Flask outputs against expected Excel/VBA results.")
    parser.add_argument("input_csv", help="CSV with model_number and expected_* columns")
    parser.add_argument("--output", "-o", default="validation/validation_report.csv", help="Output comparison CSV")
    parser.add_argument("--tolerance", type=float, default=0.01, help="Numeric comparison tolerance")
    parser.add_argument(
        "--fields",
        default="",
        help="Optional comma-separated dotted fields to compare, e.g. mca_mocp.mca,mca_mocp.mocp",
    )
    parser.add_argument("--json", action="store_true", help="Also print summary JSON")
    args = parser.parse_args()

    fields = [f.strip() for f in args.fields.split(",") if f.strip()] or None
    run = validate_csv_file(args.input_csv, fields=fields, tolerance=args.tolerance)
    output_path = write_validation_report_csv(run, PROJECT_ROOT / args.output)

    print(f"Validation status: {run.status}")
    print(f"Cases: {run.total_cases} | Passed: {run.passed_cases} | Failed: {run.failed_cases} | Skipped: {run.skipped_cases}")
    print(f"Report: {output_path}")
    if args.json:
        print(json.dumps(run.to_dict(), indent=2))

    return 1 if run.failed_cases else 0


if __name__ == "__main__":
    raise SystemExit(main())
