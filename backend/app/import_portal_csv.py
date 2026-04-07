from __future__ import annotations

import argparse
from pathlib import Path

from app.db.base import Base
from app.db.portal_csv_loader import import_portal_csv_dataset
from app.db.session import SessionLocal, engine


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Load portal CSV files into PostgreSQL."
    )
    parser.add_argument(
        "--ste-csv",
        type=Path,
        required=True,
        help="Path to the STE CSV file.",
    )
    parser.add_argument(
        "--contracts-csv",
        type=Path,
        required=True,
        help="Path to the contracts CSV file.",
    )
    parser.add_argument(
        "--no-truncate",
        action="store_true",
        help="Do not clear existing data before import.",
    )
    parser.add_argument(
        "--ste-limit",
        type=int,
        default=0,
        help="Optional limit for STE rows to import. 0 means all rows.",
    )
    parser.add_argument(
        "--contract-limit",
        type=int,
        default=0,
        help="Optional limit for contract rows to scan. 0 means all rows.",
    )
    parser.add_argument(
        "--purchase-history-limit",
        type=int,
        default=120,
        help="How many purchase history rows to generate per demo customer.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    Base.metadata.create_all(bind=engine)

    with SessionLocal() as session:
        stats = import_portal_csv_dataset(
            session=session,
            ste_csv_path=args.ste_csv.resolve(),
            contracts_csv_path=args.contracts_csv.resolve(),
            truncate=not args.no_truncate,
            ste_limit=args.ste_limit,
            contract_limit=args.contract_limit,
            purchase_history_limit=args.purchase_history_limit,
        )

    print("Portal CSV data imported successfully.")
    print(f"STE source: {args.ste_csv.resolve()}")
    print(f"Contracts source: {args.contracts_csv.resolve()}")
    for key, value in sorted(stats.items()):
        print(f"- {key}: {value}")


if __name__ == "__main__":
    main()
