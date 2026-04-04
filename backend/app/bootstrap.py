from pathlib import Path

from sqlalchemy import func, select

from app.core.config import settings
from app.db.base import Base
from app.db.models import CategoryModel, STEItemModel, SupplierModel, SynonymModel
from app.db.portal_csv_loader import import_portal_csv_dataset
from app.db.session import SessionLocal, engine


def _resolve_portal_path(configured_path: str) -> Path:
    path = Path(configured_path).expanduser()
    if path.is_absolute():
        return path

    backend_dir = Path(__file__).resolve().parents[1]
    return (backend_dir / path).resolve()


def _bootstrap_portal_csv_data() -> bool:
    ste_csv_path = _resolve_portal_path(settings.portal_ste_csv_path)
    contracts_csv_path = _resolve_portal_path(settings.portal_contracts_csv_path)
    if not ste_csv_path.exists() or not contracts_csv_path.exists():
        return False

    with SessionLocal() as session:
        truncate_import = settings.portal_import_truncate
        desired_ste_limit = settings.portal_import_ste_limit
        if not settings.portal_import_truncate:
            existing_items = int(session.execute(select(func.count(STEItemModel.id))).scalar_one() or 0)
            existing_categories = int(
                session.execute(select(func.count(CategoryModel.id))).scalar_one() or 0
            )
            existing_suppliers = int(
                session.execute(select(func.count(SupplierModel.id))).scalar_one() or 0
            )
            existing_synonyms = int(
                session.execute(select(func.count(SynonymModel.id))).scalar_one() or 0
            )
            if (
                existing_items > 0
                and existing_categories > 0
                and existing_suppliers > 0
                and existing_synonyms > 0
            ):
                if desired_ste_limit > 0 and existing_items > desired_ste_limit:
                    print(
                        "[bootstrap] Existing catalog exceeds configured STE limit. "
                        f"Resetting catalog tables and reimporting limited subset "
                        f"(existing_items={existing_items}, ste_limit={desired_ste_limit}).",
                        flush=True,
                    )
                    truncate_import = True
                else:
                    print(
                        "[bootstrap] Portal CSV import skipped: "
                        "catalog already loaded "
                        f"(items={existing_items}, categories={existing_categories}, "
                        f"suppliers={existing_suppliers}, synonyms={existing_synonyms}).",
                        flush=True,
                    )
                    return True
            if not truncate_import and any(
                count > 0
                for count in (
                    existing_items,
                    existing_categories,
                    existing_suppliers,
                    existing_synonyms,
                )
            ):
                print(
                    "[bootstrap] Partial portal import detected. "
                    "Resetting catalog tables and reimporting from CSV.",
                    flush=True,
                )
                truncate_import = True

        import_portal_csv_dataset(
            session=session,
            ste_csv_path=ste_csv_path,
            contracts_csv_path=contracts_csv_path,
            truncate=truncate_import,
            ste_limit=settings.portal_import_ste_limit,
            contract_limit=settings.portal_import_contract_limit,
            purchase_history_limit=settings.portal_import_purchase_history_limit,
        )

    return True


def bootstrap() -> None:
    Base.metadata.create_all(bind=engine)
    dataset_mode = settings.bootstrap_dataset.strip().lower()

    if dataset_mode != "portal_csv":
        raise ValueError(
            "Unsupported bootstrap dataset mode. "
            "Use only: portal_csv."
        )

    if _bootstrap_portal_csv_data():
        return
    raise FileNotFoundError(
        "Portal CSV bootstrap failed. "
        f"STE: {_resolve_portal_path(settings.portal_ste_csv_path)} | "
        f"Contracts: {_resolve_portal_path(settings.portal_contracts_csv_path)}"
    )


if __name__ == "__main__":
    bootstrap()
