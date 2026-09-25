"""
A small ML model that refines the physics-based fuel estimate.

In a production system this would be trained on real historical voyage
logs (speed, distance, wave height, vessel type -> actual fuel burned).
Here we synthesize a physically-plausible training set so the project is
runnable end-to-end without a proprietary dataset, and the model can be
retrained later by swapping `generate_synthetic_training_data()` for a
loader over real logs.
"""
import numpy as np
from sklearn.ensemble import RandomForestRegressor

from app.config import DEFAULT_FUEL_RATE_TON_PER_HR

VESSEL_TYPES = list(DEFAULT_FUEL_RATE_TON_PER_HR.keys())


def generate_synthetic_training_data(n_samples: int = 4000, seed: int = 42):
    rng = np.random.default_rng(seed)

    speed = rng.uniform(8, 28, n_samples)              # knots
    distance = rng.uniform(50, 6000, n_samples)         # nm
    wave_height = rng.uniform(0, 8, n_samples)          # m
    vessel_idx = rng.integers(0, len(VESSEL_TYPES), n_samples)
    base_rate = np.array([DEFAULT_FUEL_RATE_TON_PER_HR[VESSEL_TYPES[i]] for i in vessel_idx])

    time_hr = distance / speed
    # cubic-ish relationship between speed and fuel rate (rough naval-architecture heuristic)
    speed_factor = (speed / 18.0) ** 2.5
    wave_factor = 1 + 0.07 * wave_height

    noise = rng.normal(0, 0.05, n_samples)
    fuel_tons = base_rate * time_hr * speed_factor * wave_factor * (1 + noise)
    fuel_tons = np.clip(fuel_tons, 0, None)

    X = np.column_stack([speed, distance, wave_height, vessel_idx])
    y = fuel_tons
    return X, y


class FuelPredictor:
    def __init__(self):
        self.model = RandomForestRegressor(n_estimators=150, max_depth=12, random_state=42)
        self._fit()

    def _fit(self):
        X, y = generate_synthetic_training_data()
        self.model.fit(X, y)

    def predict(self, speed_knots: float, distance_nm: float, wave_height_m: float, vessel_type: str) -> float:
        vessel_idx = VESSEL_TYPES.index(vessel_type) if vessel_type in VESSEL_TYPES else 0
        X = np.array([[speed_knots, distance_nm, wave_height_m, vessel_idx]])
        pred = self.model.predict(X)[0]
        return float(max(pred, 0.0))


# Singleton — trained once at import time (a few hundred ms).
fuel_predictor = FuelPredictor()
