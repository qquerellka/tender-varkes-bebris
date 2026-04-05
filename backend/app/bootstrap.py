from pathlib import Path

from sqlalchemy import func, select

from app.core.config import settings
from app.db.base import Base
from app.db.models import (
    CategoryModel,
    STEItemModel,
    SupplierModel,
    SpellCorrectionModel,
    SynonymModel,
)
from app.db.portal_csv_loader import ensure_seed_spell_and_synonyms, import_portal_csv_dataset
from app.db.session import SessionLocal, engine


def _resolve_portal_path(configured_path: str) -> Path:
    path = Path(configured_path).expanduser()
    if path.is_absolute():
        return path

    backend_dir = Path(__file__).resolve().parents[1]
    return (backend_dir / path).resolve()


def _portal_data_dir() -> Path:
    backend_dir = Path(__file__).resolve().parents[1]
    return (backend_dir / "../ML/data/orig").resolve()


def _discover_portal_csv_path(*prefixes: str) -> Path | None:
    data_dir = _portal_data_dir()
    if not data_dir.exists():
        return None

    candidates: set[Path] = set()
    for prefix in prefixes:
        candidates.update(data_dir.glob(f"{prefix}_*/*.csv"))
        candidates.update(data_dir.rglob(f"{prefix}*.csv"))

    return next(iter(sorted(path.resolve() for path in candidates if path.exists())), None)


def _resolve_portal_csv_path(configured_path: str, *prefixes: str) -> Path:
    resolved = _resolve_portal_path(configured_path)
    if resolved.exists():
        return resolved

    discovered = _discover_portal_csv_path(*prefixes)
    if discovered is not None:
        print(
            "[bootstrap] Using discovered portal CSV because configured path is unavailable: "
            f"{resolved} -> {discovered}",
            flush=True,
        )
        return discovered

    return resolved


def _bootstrap_portal_csv_data() -> bool:
    ste_csv_path = _resolve_portal_csv_path(settings.portal_ste_csv_path, "СТЕ", "STE")
    contracts_csv_path = _resolve_portal_csv_path(
        settings.portal_contracts_csv_path,
        "Контракты",
        "Contracts",
    )
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
            existing_spell_corrections = int(
                session.execute(select(func.count(SpellCorrectionModel.id))).scalar_one() or 0
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
                    ensure_seed_spell_and_synonyms(session)
                    print(
                        "[bootstrap] Portal CSV import skipped: "
                        "catalog already loaded "
                        f"(items={existing_items}, categories={existing_categories}, "
                        f"suppliers={existing_suppliers}, synonyms={existing_synonyms}, "
                        f"spell_corrections={existing_spell_corrections}).",
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
                    existing_spell_corrections,
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
        f"STE: {_resolve_portal_csv_path(settings.portal_ste_csv_path, 'СТЕ', 'STE')} | "
        f"Contracts: {_resolve_portal_csv_path(settings.portal_contracts_csv_path, 'Контракты', 'Contracts')}"
    )


if __name__ == "__main__":
    bootstrap()
