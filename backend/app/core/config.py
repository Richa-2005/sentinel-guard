import os

class SystemRiskConfig:
    """Centralized enterprise system boundaries for Sentinel Guard."""
    CALIBRATED_THRESHOLD: float = float(os.getenv("RISK_THRESHOLD", 0.01))
    XGB_WEIGHT: float = 0.50
    LGB_WEIGHT: float = 0.50
    VELOCITY_WINDOW_MINUTES: int = 10
    MAX_IN_MEMORY_LEDS: int = 10000