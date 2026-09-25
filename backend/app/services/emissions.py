from app.config import CO2_PER_TON_FUEL


def co2_tons_from_fuel(fuel_tons: float) -> float:
    return fuel_tons * CO2_PER_TON_FUEL


def sustainability_score(fuel_tons: float, distance_nm: float) -> float:
    """A simple 0-100 score: lower fuel-per-nautical-mile is better.
    Calibrated against a rough industry-typical burn rate of 0.03 t/nm
    for a mid-size vessel."""
    if distance_nm <= 0:
        return 100.0
    intensity = fuel_tons / distance_nm
    baseline = 0.03
    score = 100 * (baseline / intensity) if intensity > 0 else 100.0
    return round(min(100.0, max(0.0, score)), 1)
