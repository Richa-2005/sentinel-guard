import json
import os
from pathlib import Path
from typing import Literal
from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR : str= Path(__file__).resolve().parents[1]
DATA_DIR :str = BASE_DIR / "data"
MODEL_CONFIG_PATH = DATA_DIR / "model_config.json"

def load_model_config() -> dict:
    if not MODEL_CONFIG_PATH.exists():
        return {}
    try:
        with MODEL_CONFIG_PATH.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

_MODEL_CONFIG = load_model_config()

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # API Keys
    GROQ_API_KEY: str = ""
    BASE_DIR : Path= Path(__file__).resolve().parents[1]
    DATA_DIR :Path = BASE_DIR / "data"
    MODEL_CONFIG_PATH : Path = DATA_DIR / "model_config.json"
    SENTINEL_DATABASE_PATH :Path = DATA_DIR / "sentinel_storage.db"

    # Auth & Demo
    JWT_SECRET_KEY: SecretStr | None = None
    JWT_ALGORITHM: Literal["HS256"] = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    DEMO_MODE: bool = True 

    # Model Parameters
    CALIBRATED_THRESHOLD: float = float(os.getenv("RISK_THRESHOLD", _MODEL_CONFIG.get("CALIBRATED_THRESHOLD", 0.01)))
    FEATURE_DIMENSIONS: list[str] = _MODEL_CONFIG.get("FEATURE_DIMENSIONS", [
        'amount_paise', 'card_vel_10m', 'device_card_ratio_30m', 
        'device_card_limit_crossed', 'is_known_merchant', 'is_off_hours_window'
    ])

settings = Settings()