from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Anthropic
    anthropic_api_key: str = Field(..., alias="ANTHROPIC_API_KEY")

    # Cost-aware model routing
    research_model: str = "claude-haiku-4-5-20251001"
    pm_model: str = "claude-sonnet-4-6"
    risk_model: str = "claude-sonnet-4-6"

    # Portfolio
    starting_capital: float = 1_000_000.0
    benchmark_ticker: str = "SPY"

    # Risk thresholds
    max_single_position_pct: float = 0.10
    max_sector_concentration: float = 0.30
    daily_loss_limit_pct: float = 0.02
    trade_notional_hitl_threshold: float = 50_000.0

    # Execution simulation
    slippage_bps: float = 5.0
    commission_per_share: float = 0.005

    # RAG
    chroma_persist_dir: str = "./data/chroma"
    embedding_model: str = "text-embedding-3-small"

    # Observability
    log_level: str = "INFO"
    audit_log_path: str = "./data/audit.jsonl"
    otlp_endpoint: str = ""

    # Dashboard
    dashboard_host: str = "0.0.0.0"
    dashboard_port: int = 8080

    # Reporting
    reports_dir: str = "./data/reports"


_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
