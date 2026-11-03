from models.calculation_result import CalculationResult
from .model_parser import parse_model_number
from .data_loader import load_lookup_tables
from .electrical_data import build_electrical_result
from .mca_mocp import calculate_mca_mocp


def run_calculation(model_number: str) -> CalculationResult:
    """Main Python equivalent of VBA Main()."""
    model, parse_errors = parse_model_number(model_number)
    result = CalculationResult(model=model)
    result.errors.messages.extend(parse_errors.messages)
    result.errors.clear = parse_errors.clear
    result.errors.end = parse_errors.end

    lookup_tables = load_lookup_tables()
    result.debug["lookup_tables_loaded"] = sorted(lookup_tables.keys())

    electrical, electrical_errors = build_electrical_result(model, lookup_tables)
    result.electrical = electrical
    result.errors.messages.extend(electrical_errors.messages)

    mca_mocp, mca_errors = calculate_mca_mocp(model, electrical)
    result.mca_mocp = mca_mocp
    result.errors.messages.extend(mca_errors.messages)

    # Keep clear/end consistent after merging warnings/errors.
    result.errors.clear = not any(m.severity == "error" for m in result.errors.messages)
    result.errors.end = any(m.severity == "error" for m in result.errors.messages)
    return result
