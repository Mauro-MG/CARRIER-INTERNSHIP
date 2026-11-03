from models.calculation_result import CalculationResult
from .info_plate_view import build_info_plate_view


def build_output(result: CalculationResult) -> dict:
    """Serialize calculation output for Flask JSON or templates."""
    payload = result.to_dict()
    payload["info_plate"] = build_info_plate_view(payload)
    return payload
