from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Tender Search Backend"
    app_version: str = "0.1.0"
    api_prefix: str = "/api/v1"
    ranking_mode: str = "baseline_personalized"
    ranking_provider: str = "noop"
    ml_artifacts_dir: str = "../ML/models/catboost_ranker_v1"
    bootstrap_dataset: str = "demo"
    synthetic_data_dir: str = "../ML/data/synthetic"
    synthetic_data_truncate: bool = True
    portal_ste_csv_path: str = "../СТЕ_20260403.csv"
    portal_contracts_csv_path: str = "../Контракты_20260403.csv"
    portal_import_truncate: bool = True
    portal_import_ste_limit: int = 0
    portal_import_contract_limit: int = 0
    portal_import_purchase_history_limit: int = 120
    search_semantic_backend: str = "auto"
    search_semantic_model_name: str = "BAAI/bge-m3"
    search_semantic_batch_size: int = 12
    search_semantic_max_length: int = 2048
    search_semantic_use_fp16: bool = False
    search_semantic_allow_remote_download: bool = True
    search_semantic_use_faiss: bool = True
    search_semantic_candidate_pool: int = 240
    search_semantic_dense_min_score: float = 0.2
    search_semantic_fallback_min_score: float = 0.12
    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/tender_search"
    demo_user_id: str = "user_1"
    demo_organization_id: str = "org_1"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
