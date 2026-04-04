import importlib.util
import logging
import sys
from pathlib import Path

from app.core.config import settings
from app.db.base import Base
from app.db.portal_csv_loader import import_portal_csv_dataset
from app.db.seed import seed_demo_data
from app.db.session import SessionLocal, engine

logger = logging.getLogger(__name__)


def _resolve_synthetic_data_dir() -> Path:
    configured_path = Path(settings.synthetic_data_dir).expanduser()
    if configured_path.is_absolute():
        return configured_path

    backend_dir = Path(__file__).resolve().parents[1]
    return (backend_dir / configured_path).resolve()


def _resolve_portal_path(configured_path: str) -> Path:
    path = Path(configured_path).expanduser()
    if path.is_absolute():
        return path

    backend_dir = Path(__file__).resolve().parents[1]
    return (backend_dir / path).resolve()


def _resolve_synthetic_loader_path() -> Path:
    synthetic_root = _resolve_synthetic_data_dir().parents[1]
    return (synthetic_root / "tools" / "synthetic_loader.py").resolve()


def _load_synthetic_importer():
    loader_path = _resolve_synthetic_loader_path()
    if not loader_path.exists():
        return None

    spec = importlib.util.spec_from_file_location("synthetic_loader", loader_path)
    if spec is None or spec.loader is None:
        return None

    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    try:
        spec.loader.exec_module(module)
    except Exception:
        sys.modules.pop(spec.name, None)
        raise
    return getattr(module, "import_synthetic_dataset", None)


def _bootstrap_synthetic_data() -> bool:
    import_synthetic_dataset = _load_synthetic_importer()
    if import_synthetic_dataset is None:
        return False

    data_dir = _resolve_synthetic_data_dir()
    if not data_dir.exists():
        return False

    with SessionLocal() as session:
        import_synthetic_dataset(
            session=session,
            data_dir=data_dir,
            truncate=settings.synthetic_data_truncate,
        )

    return True


def _bootstrap_portal_csv_data() -> bool:
    ste_csv_path = _resolve_portal_path(settings.portal_ste_csv_path)
    contracts_csv_path = _resolve_portal_path(settings.portal_contracts_csv_path)
    if not ste_csv_path.exists() or not contracts_csv_path.exists():
        return False

    with SessionLocal() as session:
        import_portal_csv_dataset(
            session=session,
            ste_csv_path=ste_csv_path,
            contracts_csv_path=contracts_csv_path,
            truncate=settings.portal_import_truncate,
            ste_limit=settings.portal_import_ste_limit,
            contract_limit=settings.portal_import_contract_limit,
            purchase_history_limit=settings.portal_import_purchase_history_limit,
        )

    return True


def bootstrap() -> None:
    Base.metadata.create_all(bind=engine)
    dataset_mode = settings.bootstrap_dataset.strip().lower()

    if dataset_mode == "portal_csv":
        if _bootstrap_portal_csv_data():
            return
        raise FileNotFoundError(
            "Portal CSV bootstrap failed. "
            f"STE: {_resolve_portal_path(settings.portal_ste_csv_path)} | "
            f"Contracts: {_resolve_portal_path(settings.portal_contracts_csv_path)}"
        )

    if dataset_mode == "synthetic":
        if _bootstrap_synthetic_data():
            return
        raise FileNotFoundError(
            "Synthetic dataset bootstrap failed. "
            f"Loader: {_resolve_synthetic_loader_path()} | "
            f"Data: {_resolve_synthetic_data_dir()}"
        )

    if dataset_mode == "auto":
        try:
            if _bootstrap_portal_csv_data():
                return
        except Exception as exc:
            logger.warning("Portal CSV bootstrap failed, falling back: %s", exc)

        try:
            if _bootstrap_synthetic_data():
                return
        except Exception as exc:
            logger.warning(
                "Synthetic dataset bootstrap failed, falling back to demo seed: %s",
                exc,
            )

    with SessionLocal() as session:
        seed_demo_data(session)


if __name__ == "__main__":
    bootstrap()
