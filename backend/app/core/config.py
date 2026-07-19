import json
import os
from pathlib import Path


DEFAULT_THRESHOLD = 0.01
DEFAULT_FEATURE_DIMENSIONS = [
    'amount_paise',
    'card_vel_10m',
    'device_card_ratio_30m',
    'device_card_limit_crossed',
    'is_known_merchant',
    'is_off_hours_window',
]
MODEL_CONFIG_PATH = Path(__file__).resolve().parents[2] / "data" / "model_config.json"


def load_model_config(config_path=MODEL_CONFIG_PATH) -> dict:
    """Load persisted model metadata, falling back safely before first training."""
    path = Path(config_path)
    if not path.exists():
        return {}

    try:
        with path.open("r", encoding="utf-8") as config_file:
            return json.load(config_file)
    except (OSError, json.JSONDecodeError):
        return {}


_MODEL_CONFIG = load_model_config()
_PERSISTED_THRESHOLD = _MODEL_CONFIG.get("CALIBRATED_THRESHOLD", DEFAULT_THRESHOLD)
_ACTIVE_THRESHOLD = os.getenv("RISK_THRESHOLD", _PERSISTED_THRESHOLD)

class SystemRiskConfig:
    """Centralized enterprise system boundaries for Sentinel Guard."""
    CALIBRATED_THRESHOLD: float = float(_ACTIVE_THRESHOLD)
    FEATURE_DIMENSIONS: list[str] = _MODEL_CONFIG.get(
        "FEATURE_DIMENSIONS",
        DEFAULT_FEATURE_DIMENSIONS,
    )
    XGB_WEIGHT: float = 0.50
    LGB_WEIGHT: float = 0.50
    VELOCITY_WINDOW_MINUTES: int = 10
    MAX_IN_MEMORY_LEDS: int = 10000
