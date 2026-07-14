from pydantic_settings import BaseSettings
from pathlib import Path

class Settings(BaseSettings):
    
    BASE_DIR : Path = Path(__file__).resolve().parents[1]
    DATA_DIR : Path = BASE_DIR / "data"
    LOG_FILE_PATH : Path = DATA_DIR / "compliance_audit.log"

settings = Settings()

