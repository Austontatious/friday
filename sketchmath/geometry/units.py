from __future__ import annotations

import math


def normalize_length(value: float, unit: str) -> float:
    normalized = unit.strip().lower()
    if normalized in {"mm", "millimeter", "millimeters"}:
        return float(value)
    if normalized in {"cm", "centimeter", "centimeters"}:
        return float(value) * 10.0
    if normalized in {"m", "meter", "meters"}:
        return float(value) * 1000.0
    raise ValueError(f"Unsupported length unit: {unit}")


def denormalize_length(value_mm: float, unit: str) -> float:
    normalized = unit.strip().lower()
    if normalized in {"mm", "millimeter", "millimeters"}:
        return float(value_mm)
    if normalized in {"cm", "centimeter", "centimeters"}:
        return float(value_mm) / 10.0
    if normalized in {"m", "meter", "meters"}:
        return float(value_mm) / 1000.0
    raise ValueError(f"Unsupported length unit: {unit}")


def normalize_angle(value: float, unit: str) -> float:
    normalized = unit.strip().lower()
    if normalized in {"deg", "degree", "degrees"}:
        return math.radians(float(value))
    if normalized in {"rad", "radian", "radians"}:
        return float(value)
    raise ValueError(f"Unsupported angle unit: {unit}")


def denormalize_angle(value_radians: float, unit: str) -> float:
    normalized = unit.strip().lower()
    if normalized in {"deg", "degree", "degrees"}:
        return math.degrees(float(value_radians))
    if normalized in {"rad", "radian", "radians"}:
        return float(value_radians)
    raise ValueError(f"Unsupported angle unit: {unit}")
