from .records import ComparisonItem, ParseResult


NEEDS_TO_BE_ADDED = "NEEDS_TO_BE_ADDED"
NEEDS_TO_BE_DELETED = "NEEDS_TO_BE_DELETED"
NO_CHANGE = "NO_CHANGE"


def _first_by_part(result: ParseResult):
    return {record.normalized_part_number: record for record in result.records if record.normalized_part_number}


def compare(parsed: dict[str, ParseResult]) -> dict[str, list[ComparisonItem]]:
    indexes = {dataset: _first_by_part(result) for dataset, result in parsed.items()}
    all_parts = set().union(*(set(index) for index in indexes.values()))
    output = {NEEDS_TO_BE_ADDED: [], NEEDS_TO_BE_DELETED: [], NO_CHANGE: []}

    for part_number in sorted(all_parts):
        in_adds = part_number in indexes["adds"]
        in_deletes = part_number in indexes["deletes"]
        in_standard = part_number in indexes["standard"]
        in_sap = part_number in indexes["sap"]

        if in_deletes and (in_sap or in_standard):
            status = NEEDS_TO_BE_DELETED
            record = indexes["deletes"][part_number]
            reason = "Listed for deletion and currently present in SAP Data or the Standard BOM."
        elif in_adds and not in_sap and not in_standard:
            status = NEEDS_TO_BE_ADDED
            record = indexes["adds"][part_number]
            reason = "Listed for addition and absent from both SAP Data and the Standard BOM."
        else:
            status = NO_CHANGE
            record = next(indexes[name][part_number] for name in ("sap", "standard", "adds", "deletes", "tumbling") if part_number in indexes[name])
            if in_adds:
                reason = "Already present in SAP Data or the Standard BOM; no add action is needed."
            elif in_deletes:
                reason = "Listed for deletion but absent from SAP Data and the Standard BOM."
            else:
                reason = "Not listed for an Add or Delete action."

        output[status].append(
            ComparisonItem(
                status=status,
                normalized_part_number=part_number,
                part_number=record.part_number,
                record=record.original_line,
                dataset=record.dataset,
                reason=reason,
                values=dict(record.values),
            )
        )
    return output
