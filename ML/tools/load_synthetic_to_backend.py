from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
BACKEND_DIR = ROOT_DIR / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.db.base import Base
from app.db.session import SessionLocal, engine

from synthetic_loader import import_synthetic_dataset


DEFAULT_DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "synthetic"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Load synthetic CSV dataset into PostgreSQL."
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=DEFAULT_DATA_DIR,
        help="Directory that contains generated synthetic CSV files.",
    )
    parser.add_argument(
        "--no-truncate",
        action="store_true",
        help="Do not clear existing tables before import.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    data_dir = args.data_dir.resolve()

    Base.metadata.create_all(bind=engine)

    with SessionLocal() as session:
        stats = import_synthetic_dataset(
            session=session,
            data_dir=data_dir,
            truncate=not args.no_truncate,
        )

    print("Synthetic data imported successfully.")
    print(f"Source: {data_dir}")
    for table_name, row_count in stats.items():
        print(f"- {table_name}: {row_count}")


if __name__ == "__main__":
    main()
