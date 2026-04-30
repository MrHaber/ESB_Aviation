import argparse
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.aviation.generator import SyntheticAviationMessageGenerator
from app.aviation.repository import AviationMessageRepository

DEFAULT_DB_PATH = "resources/synthetic_aviation_messages.db"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate a SQLite database with synthetic aviation operational messages."
    )
    parser.add_argument("--count", type=int, default=250)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--db-path", default=DEFAULT_DB_PATH)
    parser.add_argument("--include-real-data", action="store_true")
    args = parser.parse_args()

    db_path = Path(args.db_path)
    generator = SyntheticAviationMessageGenerator(seed=args.seed)
    repository = AviationMessageRepository(db_path)
    inserted = repository.replace_messages(
        generator.generate(count=args.count, include_real_data=args.include_real_data)
    )

    print(f"Generated {inserted} synthetic aviation messages in {db_path}")


if __name__ == "__main__":
    main()
