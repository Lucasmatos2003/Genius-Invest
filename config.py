import os
from dataclasses import dataclass
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent
ENV_PATH = ROOT_DIR / ".env"


def load_env(path: str | Path = ENV_PATH) -> dict[str, str]:
    values: dict[str, str] = {}
    env_file = Path(path)

    if env_file.exists():
        for raw_line in env_file.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue

            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            values[key] = value
            os.environ.setdefault(key, value)

    return values


@dataclass(frozen=True)
class Settings:
    gemini_api_key: str
    gemini_model: str = "gemini-flash-latest"
    gemini_per_model_timeout: int = 12
    finance_cache_ttl: int = 300


def get_settings() -> Settings:
    load_env()
    gemini_api_key = os.getenv("GEMINI_API_KEY", "").strip()
    gemini_model = os.getenv("GEMINI_MODEL", "gemini-flash-latest").strip() or "gemini-flash-latest"
    try:
        gemini_per_model_timeout = int(os.getenv("GEMINI_PER_MODEL_TIMEOUT", "12"))
    except ValueError:
        gemini_per_model_timeout = 12
    try:
        finance_cache_ttl = int(os.getenv("FINANCE_CACHE_TTL", "300"))
    except ValueError:
        finance_cache_ttl = 300

    if not gemini_api_key or gemini_api_key == "your_api_key_here":
        raise ValueError("A variável GEMINI_API_KEY não foi definida no arquivo .env.")

    return Settings(
        gemini_api_key=gemini_api_key,
        gemini_model=gemini_model,
        gemini_per_model_timeout=gemini_per_model_timeout,
        finance_cache_ttl=finance_cache_ttl,
    )
