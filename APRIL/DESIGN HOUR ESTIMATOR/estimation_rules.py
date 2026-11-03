"""Shared design-hour weighting rules used by both applications."""

from __future__ import annotations


PRIMARY_L1_WEIGHT = 1.0
SECONDARY_L1_WEIGHT = 0.25
TERTIARY_L1_WEIGHT = 0.10


def weighted_quantity_multiplier(
    primary_quantity: float,
    secondary_quantity: float,
    tertiary_quantity: float,
) -> float:
    return (
        primary_quantity * PRIMARY_L1_WEIGHT
        + secondary_quantity * SECONDARY_L1_WEIGHT
        + tertiary_quantity * TERTIARY_L1_WEIGHT
    )


def weighted_hour_components(
    base_hours: float,
    primary_quantity: float,
    secondary_quantity: float,
    tertiary_quantity: float,
) -> tuple[float, float, float]:
    return (
        base_hours * primary_quantity * PRIMARY_L1_WEIGHT,
        base_hours * secondary_quantity * SECONDARY_L1_WEIGHT,
        base_hours * tertiary_quantity * TERTIARY_L1_WEIGHT,
    )


def weighted_hours(
    base_hours: float,
    primary_quantity: float,
    secondary_quantity: float,
    tertiary_quantity: float,
) -> float:
    return sum(
        weighted_hour_components(
            base_hours,
            primary_quantity,
            secondary_quantity,
            tertiary_quantity,
        )
    )
