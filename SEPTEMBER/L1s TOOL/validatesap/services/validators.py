from collections import defaultdict

from .normalization import derive_source
from .parsers import SPECS
from .records import ParseResult, ValidationMessage


REQUIRED_DATASETS = ("standard", "sap")


def _label(dataset: str) -> str:
    return {"sap": "SAP Data", "standard": "Standard BOM"}.get(dataset, dataset.title())


def validate(parsed: dict[str, ParseResult]) -> list[ValidationMessage]:
    messages = [message for result in parsed.values() for message in result.messages]

    for dataset in REQUIRED_DATASETS:
        if not parsed[dataset].records:
            messages.append(
                ValidationMessage(dataset=dataset, message=f"{_label(dataset)} is required and contains no data rows.", code="missing_dataset")
            )

    for dataset, result in parsed.items():
        seen: dict[str, list[int]] = defaultdict(list)
        for record in result.records:
            if not record.normalized_part_number:
                messages.append(
                    ValidationMessage(dataset=dataset, row_number=record.row_number, message="Part number is required.", code="missing_part_number")
                )
            else:
                seen[record.normalized_part_number].append(record.row_number)

            for field in SPECS[dataset].required_fields:
                if field in {"part_number", "quantity", "source"}:
                    continue
                if not record.values.get(field, "").strip():
                    messages.append(
                        ValidationMessage(
                            dataset=dataset,
                            row_number=record.row_number,
                            part_number=record.part_number,
                            message=f"Required field '{field.replace('_', ' ').title()}' is blank.",
                            code="missing_required_field",
                        )
                    )

            if "quantity" in record.values:
                raw_quantity = record.values.get("quantity", "")
                if record.quantity is None:
                    messages.append(
                        ValidationMessage(
                            dataset=dataset,
                            row_number=record.row_number,
                            part_number=record.part_number,
                            message=f"Quantity '{raw_quantity}' is not numeric.",
                            code="invalid_quantity",
                        )
                    )
                elif record.quantity <= 0:
                    messages.append(
                        ValidationMessage(
                            dataset=dataset,
                            row_number=record.row_number,
                            part_number=record.part_number,
                            message="Quantity must be greater than zero.",
                            code="invalid_quantity",
                        )
                    )

            if dataset == "sap":
                source = derive_source(record.values.get("source_code_1", ""), record.values.get("source_code_2", ""))
                if source is None:
                    messages.append(
                        ValidationMessage(
                            dataset=dataset,
                            row_number=record.row_number,
                            part_number=record.part_number,
                            message="Invalid SAP source-code pair. Allowed pairs are blank/blank (R), 50/50 (M), or 0/0 (B).",
                            code="invalid_source_pair",
                        )
                    )

            if dataset == "adds" and record.values.get("source", "").upper() not in {"R", "M", "B"}:
                messages.append(
                    ValidationMessage(
                        dataset=dataset,
                        row_number=record.row_number,
                        part_number=record.part_number,
                        message="Add source must be R, M, or B.",
                        code="invalid_add_source",
                    )
                )

        for normalized_pn, rows in seen.items():
            if len(rows) > 1:
                messages.append(
                    ValidationMessage(
                        dataset=dataset,
                        row_number=rows[0],
                        part_number=normalized_pn,
                        message=f"Duplicate part number appears on rows {', '.join(map(str, rows))}.",
                        code="duplicate_part_number",
                    )
                )

    add_parts = {record.normalized_part_number for record in parsed["adds"].records if record.normalized_part_number}
    delete_parts = {record.normalized_part_number for record in parsed["deletes"].records if record.normalized_part_number}
    for part_number in sorted(add_parts & delete_parts):
        messages.append(
            ValidationMessage(
                dataset="conflicts",
                part_number=part_number,
                message="Part number is present in both Adds and Deletes. Resolve the conflict before comparison.",
                code="add_delete_conflict",
            )
        )
    return messages
