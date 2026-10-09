"""SQLite connection, schema migrations and backups.

- ``connect()`` returns a connection that commits *and closes* when used as a
  context manager (plain sqlite3 connections only commit, leaking handles).
- Migrations are versioned with ``PRAGMA user_version``. Before migrating an
  existing database a full snapshot is written to ``data/backups``.
- ``snapshot()`` uses the online backup API, so it is consistent even while
  the app (or the Strava thread) is writing.
- Before migrating, rows pointing at deleted foods are repaired, and
  pre-existing foreign-key problems never block an upgrade.
"""

from __future__ import annotations

import re
import sqlite3
import threading
import time
from datetime import date, datetime
from pathlib import Path
from typing import Callable

import dpp_config as config


class ClosingConnection(sqlite3.Connection):
    """``with connect() as db:`` commits on success, rolls back on error, then closes."""

    def __exit__(self, exc_type, exc, tb):
        try:
            return super().__exit__(exc_type, exc, tb)
        finally:
            self.close()


def connect(path: Path | str | None = None) -> sqlite3.Connection:
    db = sqlite3.connect(str(path or config.DB_PATH), timeout=15, factory=ClosingConnection)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys = ON")
    db.execute("PRAGMA busy_timeout = 15000")
    return db


def _table_exists(db: sqlite3.Connection, table: str) -> bool:
    return db.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
    ).fetchone() is not None


def qident(name: str) -> str:
    """Quote an SQL identifier. Identifiers are never taken from requests: callers pass
    literals or names read from sqlite_master/PRAGMA, and this keeps even those inert."""
    return '"' + str(name).replace('"', '""') + '"'


def _columns(db: sqlite3.Connection, table: str) -> list[str]:
    return [row[1] for row in db.execute(f"PRAGMA table_info({qident(table)})").fetchall()]


# ---------------------------------------------------------------------------
# Migrations
# ---------------------------------------------------------------------------

_UNIQUE_MEALS_RE = re.compile(
    r",\s*UNIQUE\s*\(\s*[\"`]?date[\"`]?\s*,\s*[\"`]?time[\"`]?\s*,\s*[\"`]?name[\"`]?\s*,\s*[\"`]?notes[\"`]?\s*\)",
    re.I,
)


def _m1_meals_without_unique(db: sqlite3.Connection) -> None:
    """Drop UNIQUE(date,time,name,notes) on meals.

    With that constraint, saving a second meal with the same date, time, type
    and notes silently merged into the first one and discarded its items.
    Follows SQLite's documented table-rebuild procedure: ids, AUTOINCREMENT
    counter, indexes, triggers and views on ``meals`` are preserved.
    """
    if not _table_exists(db, "meals"):
        return
    row = db.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='meals'").fetchone()
    sql = str(row[0] or "")
    new_sql, count = _UNIQUE_MEALS_RE.subn("", sql)
    if not count:
        return
    new_sql = re.sub(r"^CREATE TABLE\s+[\"`]?meals[\"`]?", "CREATE TABLE meals__new", new_sql, count=1, flags=re.I)
    # Objects to recreate after the rebuild (DROP TABLE removes indexes/triggers;
    # views referencing meals would make the RENAME fail, so drop them first).
    dependents = db.execute(
        "SELECT type, name, sql FROM sqlite_master WHERE sql IS NOT NULL AND name <> 'meals' AND ("
        " (type IN ('index', 'trigger') AND tbl_name = 'meals') OR"
        " (type = 'view' AND lower(sql) LIKE '%meals%'))"
    ).fetchall()
    seq_row = db.execute("SELECT seq FROM sqlite_sequence WHERE name='meals'").fetchone() if _table_exists(db, "sqlite_sequence") else None
    for kind, name, _sql in dependents:
        if kind == "view":
            db.execute(f"DROP VIEW IF EXISTS {qident(name)}")
    cols = ", ".join(qident(c) for c in _columns(db, "meals"))
    db.execute(new_sql)
    db.execute(f"INSERT INTO meals__new({cols}) SELECT {cols} FROM meals")
    db.execute("DROP TABLE meals")
    db.execute("ALTER TABLE meals__new RENAME TO meals")
    for kind, _name, dep_sql in sorted(dependents, key=lambda item: {"index": 0, "view": 1, "trigger": 2}[item[0]]):
        db.execute(dep_sql)
    if seq_row is not None:
        # Keep the AUTOINCREMENT high-water mark so ids of deleted meals are never reused.
        db.execute("UPDATE sqlite_sequence SET seq = MAX(seq, ?) WHERE name='meals'", (int(seq_row[0]),))
        if not db.execute("SELECT 1 FROM sqlite_sequence WHERE name='meals'").fetchone():
            db.execute("INSERT INTO sqlite_sequence(name, seq) VALUES('meals', ?)", (int(seq_row[0]),))


def _m2_indexes_and_workout_source(db: sqlite3.Connection) -> None:
    """Indexes for date lookups + explicit source/external_id on workouts.

    Strava de-duplication used ``notes LIKE '%id=…%'`` table scans; the
    external id now lives in its own indexed column (notes are kept as-is).
    """
    if _table_exists(db, "meals"):
        db.execute("CREATE INDEX IF NOT EXISTS idx_meals_date ON meals(date, time)")
    if _table_exists(db, "meal_items"):
        db.execute("CREATE INDEX IF NOT EXISTS idx_meal_items_meal ON meal_items(meal_id)")
    if _table_exists(db, "weights"):
        db.execute("CREATE INDEX IF NOT EXISTS idx_weights_date ON weights(date, time)")
    if _table_exists(db, "body_composition") and "date" in _columns(db, "body_composition"):
        db.execute("CREATE INDEX IF NOT EXISTS idx_body_composition_date ON body_composition(date)")
    if not _table_exists(db, "workouts"):
        return
    cols = _columns(db, "workouts")
    if "source" not in cols:
        db.execute("ALTER TABLE workouts ADD COLUMN source TEXT NOT NULL DEFAULT ''")
    if "external_id" not in cols:
        db.execute("ALTER TABLE workouts ADD COLUMN external_id TEXT NOT NULL DEFAULT ''")
    pattern = re.compile(r"\bid=(\d+)")
    for row in db.execute("SELECT id, notes FROM workouts WHERE notes LIKE '%id=%'").fetchall():
        notes = str(row[1] or "")
        match = pattern.search(notes)
        if match and notes.lower().startswith("strava"):
            db.execute(
                "UPDATE workouts SET source='strava', external_id=? WHERE id=?",
                (match.group(1), row[0]),
            )
    db.execute("CREATE INDEX IF NOT EXISTS idx_workouts_date ON workouts(date, time)")
    db.execute("CREATE INDEX IF NOT EXISTS idx_workouts_external ON workouts(source, external_id)")


def _m3_settings_and_ai_tables(db: sqlite3.Connection) -> None:
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS app_settings(
          key TEXT PRIMARY KEY,
          value TEXT NOT NULL DEFAULT '{}',
          updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS ai_cache(
          key TEXT PRIMARY KEY,
          kind TEXT NOT NULL,
          response TEXT NOT NULL,
          created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS ai_usage(
          day TEXT NOT NULL,
          kind TEXT NOT NULL,
          calls INTEGER NOT NULL DEFAULT 0,
          input_tokens INTEGER NOT NULL DEFAULT 0,
          output_tokens INTEGER NOT NULL DEFAULT 0,
          PRIMARY KEY(day, kind)
        )
        """
    )


def _m4_food_barcode(db: sqlite3.Connection) -> None:
    if not _table_exists(db, "foods"):
        return
    if "barcode" not in _columns(db, "foods"):
        db.execute("ALTER TABLE foods ADD COLUMN barcode TEXT NOT NULL DEFAULT ''")
    db.execute("CREATE INDEX IF NOT EXISTS idx_foods_barcode ON foods(barcode)")


def _m5_repair_zero_macro_items(db: sqlite3.Connection) -> None:
    """Fill macros for meal items stored with grams but no nutrition.

    Some locally imported meals carried only food + grams; the UI used to
    patch them on the fly from Food Intelligence. Repair the data once,
    from the catalog (by food_id, else by exact name).
    """
    if not (_table_exists(db, "meal_items") and _table_exists(db, "foods")):
        return
    rows = db.execute(
        """
        SELECT i.id, i.grams, f.kcal, f.protein, f.carbs, f.fat, f.sugar, f.salt
        FROM meal_items i
        JOIN foods f ON f.id = i.food_id OR (i.food_id IS NULL AND f.name = i.food_name)
        WHERE i.grams > 0 AND f.kcal > 0
          AND COALESCE(i.kcal, 0) = 0 AND COALESCE(i.protein, 0) = 0
          AND COALESCE(i.carbs, 0) = 0 AND COALESCE(i.fat, 0) = 0
        """
    ).fetchall()
    for row in rows:
        k = float(row[1]) / 100.0
        db.execute(
            "UPDATE meal_items SET kcal=?, protein=?, carbs=?, fat=?, sugar=?, salt=? WHERE id=?",
            (round(row[2] * k, 1), round(row[3] * k, 1), round(row[4] * k, 1), round(row[5] * k, 1),
             round(row[6] * k, 1), round(row[7] * k, 2), row[0]),
        )


MIGRATIONS: list[tuple[int, str, Callable[[sqlite3.Connection], None]]] = [
    (1, "meals without UNIQUE constraint", _m1_meals_without_unique),
    (2, "indexes + workouts.source/external_id", _m2_indexes_and_workout_source),
    (3, "app_settings + AI cache/usage tables", _m3_settings_and_ai_tables),
    (4, "foods.barcode", _m4_food_barcode),
    (5, "repair meal items stored without macros", _m5_repair_zero_macro_items),
]
SCHEMA_VERSION = MIGRATIONS[-1][0]


def user_version(path: Path | str | None = None) -> int:
    with connect(path) as db:
        return int(db.execute("PRAGMA user_version").fetchone()[0])


def has_user_data(path: Path | str | None = None) -> bool:
    target = Path(path or config.DB_PATH)
    if not target.exists() or target.stat().st_size == 0:
        return False
    with connect(target) as db:
        for table in ("meals", "weights", "workouts"):
            if _table_exists(db, table) and db.execute(f"SELECT 1 FROM {qident(table)} LIMIT 1").fetchone():
                return True
    return False


def _repair_dangling_references(db: sqlite3.Connection) -> int:
    """Null out meal_items.food_id pointing at deleted foods (what ON DELETE SET NULL would have done).

    Old local scripts deleted foods with foreign keys off, leaving such rows.
    """
    if not (_table_exists(db, "meal_items") and _table_exists(db, "foods")):
        return 0
    cur = db.execute(
        "UPDATE meal_items SET food_id = NULL WHERE food_id IS NOT NULL AND food_id NOT IN (SELECT id FROM foods)"
    )
    return cur.rowcount or 0


def _fk_violations(db: sqlite3.Connection) -> set[tuple]:
    return {tuple(row) for row in db.execute("PRAGMA foreign_key_check").fetchall()}


def migrate(path: Path | str | None = None, backup: bool = True) -> list[int]:
    """Apply pending migrations; returns the versions applied."""
    target = Path(path or config.DB_PATH)
    current = user_version(target)
    pending = [m for m in MIGRATIONS if m[0] > current]
    if not pending:
        return []
    label = f"pre-migration-v{current}-to-v{pending[-1][0]}"
    folder = Path(config.BACKUPS_DIR)
    already_saved = folder.exists() and any(folder.glob(f"dieta-*-{label}.db"))
    if backup and has_user_data(target) and not already_saved:
        # Only once per version jump: a failing start must not fill the SD card with copies.
        snapshot(target, label=label)

    db = sqlite3.connect(str(target), timeout=15, isolation_level=None)
    applied: list[int] = []
    try:
        # foreign_keys must be OFF while rebuilding tables, otherwise DROP TABLE
        # would cascade-delete child rows. It cannot change inside a transaction.
        db.execute("PRAGMA foreign_keys = OFF")
        db.execute("BEGIN IMMEDIATE")
        repaired = _repair_dangling_references(db)
        db.execute("COMMIT")
        if repaired:
            print(f"[DPP] repaired {repaired} meal item(s) pointing at deleted foods")
        # Pre-existing problems (e.g. orphan rows from old scripts) must not block
        # the upgrade; only violations introduced by a migration abort it.
        baseline = _fk_violations(db)
        for version, _label, fn in pending:
            db.execute("BEGIN IMMEDIATE")
            try:
                fn(db)
                problems = _fk_violations(db) - baseline
                if problems:
                    raise RuntimeError(f"foreign key check failed after migration {version}: {sorted(problems)[:5]}")
                db.execute(f"PRAGMA user_version = {int(version)}")
                db.execute("COMMIT")
                applied.append(version)
            except Exception:
                db.execute("ROLLBACK")
                raise
    finally:
        db.execute("PRAGMA foreign_keys = ON")
        db.close()
    return applied


def ensure_rollback_journal(path: Path | str | None = None) -> None:
    """Keep the classic single-file journal (not WAL).

    With WAL, recent commits live in dieta.db-wal and a plain ``cp dieta.db``
    (used by local maintenance scripts and manual backups) silently misses
    them. busy_timeout already covers the background Strava thread. Also
    converts back any database left in WAL mode by a pre-release build.
    """
    try:
        db = sqlite3.connect(str(path or config.DB_PATH), timeout=15)
        mode = db.execute("PRAGMA journal_mode").fetchone()[0]
        if str(mode).lower() == "wal":
            db.execute("PRAGMA journal_mode = DELETE")
        db.close()
    except sqlite3.DatabaseError as exc:
        print(f"[DPP] journal mode not checked: {exc}")


# ---------------------------------------------------------------------------
# Backups
# ---------------------------------------------------------------------------

_BACKUP_LOCK = threading.Lock()


def snapshot(path: Path | str | None = None, label: str = "manual", dest_dir: Path | None = None) -> Path:
    source_path = Path(path or config.DB_PATH)
    folder = Path(dest_dir or config.BACKUPS_DIR)
    folder.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    safe_label = re.sub(r"[^a-zA-Z0-9_.-]+", "-", label).strip("-") or "backup"
    target = folder / f"dieta-{stamp}-{safe_label}.db"
    with _BACKUP_LOCK:
        src = sqlite3.connect(str(source_path), timeout=15)
        dst = sqlite3.connect(str(target))
        try:
            src.backup(dst)
        finally:
            dst.close()
            src.close()
    try:
        target.chmod(0o600)
    except OSError:
        pass
    return target


def list_backups(dest_dir: Path | None = None) -> list[dict]:
    folder = Path(dest_dir or config.BACKUPS_DIR)
    if not folder.exists():
        return []
    items = []
    for file in sorted(folder.glob("dieta-*.db"), reverse=True):
        stat = file.stat()
        items.append({
            "name": file.name,
            "size_kb": round(stat.st_size / 1024, 1),
            "created_at": datetime.fromtimestamp(stat.st_mtime).isoformat(timespec="seconds"),
        })
    return items


def prune_daily_backups(keep: int | None = None, dest_dir: Path | None = None) -> int:
    keep = config.BACKUP_KEEP if keep is None else keep
    folder = Path(dest_dir or config.BACKUPS_DIR)
    daily = sorted(folder.glob("dieta-*-daily.db"), reverse=True) if folder.exists() else []
    removed = 0
    for old in daily[keep:]:
        old.unlink(missing_ok=True)
        removed += 1
    return removed


def daily_backup_if_due(path: Path | str | None = None) -> Path | None:
    if config.BACKUP_KEEP <= 0 or not has_user_data(path):
        return None
    folder = config.BACKUPS_DIR
    today = date.today().strftime("%Y%m%d")
    if folder.exists() and any(folder.glob(f"dieta-{today}-*-daily.db")):
        return None
    created = snapshot(path, label="daily")
    prune_daily_backups()
    return created


_BACKUP_THREAD_STARTED = False


def start_backup_thread() -> None:
    global _BACKUP_THREAD_STARTED
    if _BACKUP_THREAD_STARTED or config.BACKUP_KEEP <= 0:
        return
    _BACKUP_THREAD_STARTED = True

    def loop() -> None:
        while True:
            try:
                daily_backup_if_due()
            except Exception as exc:  # never let the backup thread die
                print(f"[DPP] daily backup failed: {exc}")
            time.sleep(3600)

    threading.Thread(target=loop, name="dpp-daily-backup", daemon=True).start()
