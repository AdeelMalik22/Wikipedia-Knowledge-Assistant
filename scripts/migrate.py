"""Apply the local SQL migrations to PostgreSQL."""

from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from app.core.database import get_connection


def main() -> None:
    migrations_dir = PROJECT_ROOT / "migrations"
    migrations = sorted(migrations_dir.glob("*.sql"))
    if not migrations:
        raise RuntimeError(f"No migrations found in {migrations_dir}")

    with get_connection() as connection:
        for migration in migrations:
            print(f"Applying {migration.name}...")
            connection.execute(migration.read_text(encoding="utf-8"))
    print("Database migrations complete.")


if __name__ == "__main__":
    main()
