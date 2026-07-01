from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# src/autojob/config/settings.py -> parents[3] = repo root (E:\Projects\AutoJob)
REPO_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    """Configurazione centrale. Override via env ``AUTOJOB_*`` o file ``.env``."""

    model_config = SettingsConfigDict(
        env_prefix="AUTOJOB_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- Daemon ---
    host: str = "127.0.0.1"
    port: int = 8765
    log_level: str = "INFO"

    # --- Storage ---
    data_dir: Path = REPO_ROOT / "data"
    db_path: Path | None = None
    cv_path: Path | None = None  # CV di default per parse_cv()

    # --- Embeddings (endpoint OpenAI-compatible: LM Studio / Ollama) ---
    embed_dim: int = 1024
    embed_model: str = "bge-m3"
    embed_base_url: str = "http://127.0.0.1:1234/v1"
    embed_api_key: str = "not-needed"

    # --- Generazione ---
    llm_provider: str = "lm_studio"  # lm_studio | ollama | agent
    llm_base_url: str = "http://127.0.0.1:1234/v1"
    llm_model: str = ""
    llm_api_key: str = "not-needed"

    # --- Browser driver MVP ---
    browser_driver: str = "fake"  # fake | playwright | cdp_mcp | claude_chrome | extension
    cdp_url: str | None = None  # se valorizzato: connect_over_cdp alla Chrome reale loggata
    browser_headless: bool = True

    # --- Candidature ---
    submit_mode: str = "manual"  # manual | semi | auto
    reapply_policy: str = "warn"  # block | warn | allow

    # --- Lifecycle (LM Studio autostart + idle shutdown) ---
    lms_autostart: bool = True
    lms_cli: str = "lms"
    lms_model: str = ""  # modello chat da caricare; fallback su llm_model
    # Caricamento modello: contesto ridotto (la KV-cache a 262k satura la VRAM → offload → lentezza)
    # e full GPU offload. 0/"" = usa i default di LM Studio.
    lms_context_length: int = 32768
    lms_gpu: str = "max"
    idle_shutdown_enabled: bool = True
    idle_shutdown_minutes: int = 30

    @property
    def db_file(self) -> Path:
        return self.db_path if self.db_path is not None else (self.data_dir / "autojob.db")

    @property
    def database_url(self) -> str:
        return f"sqlite:///{self.db_file.as_posix()}"

    @property
    def repo_root(self) -> Path:
        return REPO_ROOT


@lru_cache
def get_settings() -> Settings:
    return Settings()
