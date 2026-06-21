"""Configuration management for united-flight-monitor.

All parameters loaded from .env with sensible defaults.
"""

from pathlib import Path
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- Credentials ---
    united_mp_number: Optional[str] = None
    united_password: Optional[str] = None

    # --- Search parameters ---
    search_origin: str = "SFO"
    search_destination: str = "BJS"
    search_start_date: str = ""
    search_end_date: str = ""
    search_cabin: str = "business"

    # --- Filter parameters ---
    max_miles: int = 110000
    exclude_airports: str = "MNL"  # comma-separated IATA codes

    # --- Browser settings ---
    browser_headless: bool = True
    browser_timeout_ms: int = 90000
    search_delay_seconds: float = 60.0

    # --- Storage ---
    data_dir: str = "~/.united_monitor"

    # --- Email ---
    email_to: Optional[str] = None
    email_from: Optional[str] = None
    email_smtp_host: str = ""
    email_smtp_port: int = 465
    email_smtp_user: Optional[str] = None
    email_smtp_password: Optional[str] = None

    # --- Computed properties ---

    @property
    def data_path(self) -> Path:
        p = Path(self.data_dir).expanduser()
        p.mkdir(parents=True, exist_ok=True)
        return p

    @property
    def logs_dir(self) -> Path:
        d = self.data_path / "logs"
        d.mkdir(parents=True, exist_ok=True)
        return d

    @property
    def cookies_dir(self) -> Path:
        d = self.data_path / "cookies"
        d.mkdir(parents=True, exist_ok=True)
        return d

    @property
    def sessions_dir(self) -> Path:
        d = self.data_path / "sessions"
        d.mkdir(parents=True, exist_ok=True)
        return d

    @property
    def exclude_airports_list(self) -> list[str]:
        return [s.strip().upper() for s in self.exclude_airports.split(",") if s.strip()]


settings = Settings()
