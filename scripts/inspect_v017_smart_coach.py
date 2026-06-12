import json
import os
import re
import sqlite3
from pathlib import Path

DB = Path("data/dieta.db")

def section(title):
    print("\n" + "=" * 80)
    print(title)
    print("=" * 80)

def table_info(cur, table):
    return cur.execute(f'PRAGMA table_info("{table}")').fetchall()

def main():
    section("Repo")
    print("cwd:", os.getcwd())
    print("db exists:", DB.exists())

    section("Python/backend files")
    for p in sorted(Path(".").glob("*.py")):
        print("-", p)
    for p in sorted(Path(".").glob("dpp_*.py")):
        print("-", p)

    section("Static files size")
    for p in [Path("static/app.js"), Path("static/styles.css")]:
        if p.exists():
            print(p, "lines:", sum(1 for _ in p.open("r", encoding="utf-8", errors="ignore")))

    if DB.exists():
        conn = sqlite3.connect(DB)
        cur = conn.cursor()

        section("SQLite tables")
        tables = [r[0] for r in cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name").fetchall()]
        for t in tables:
            print("-", t)

        section("Tables with body/bio/metric candidates")
        keywords = ["bio", "hybrid", "charge", "body", "metric", "snapshot", "weight", "composition"]
        for t in tables:
            cols = table_info(cur, t)
            names = [c[1] for c in cols]
            blob = (t + " " + " ".join(names)).lower()
            if any(k in blob for k in keywords):
                print("\nTABLE", t)
                for c in cols:
                    print(" ", c)

        section("Recent body/bio-like rows")
        for t in tables:
            cols = [c[1] for c in table_info(cur, t)]
            blob = (t + " " + " ".join(cols)).lower()
            if any(k in blob for k in ["biocharge", "hybrid", "body", "metric"]):
                try:
                    rows = cur.execute(f'SELECT * FROM "{t}" LIMIT 5').fetchall()
                    print("\nTABLE", t, "rows:", len(rows))
                    print("columns:", cols)
                    for r in rows[:3]:
                        print(r)
                except Exception as e:
                    print("ERR reading", t, e)

        conn.close()

    section("Route scan")
    route_re = re.compile(r'@.*\.route\([\'"]([^\'"]+)')
    for p in sorted(Path(".").glob("*.py")) + sorted(Path(".").glob("dpp_*.py")):
        try:
            txt = p.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        routes = route_re.findall(txt)
        if routes:
            print("\n", p)
            for r in routes:
                print(" ", r)

    section("Smart coach relevant grep")
    patterns = ["food-intel", "body-snapshot", "body-trends", "strava", "weights", "BioCharge", "Hybrid"]
    for pat in patterns:
        print(f"\n--- {pat} ---")
        for p in sorted(Path(".").glob("*.py")) + sorted(Path(".").glob("dpp_*.py")):
            try:
                txt = p.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue
            if pat.lower() in txt.lower():
                print(p)

if __name__ == "__main__":
    main()
