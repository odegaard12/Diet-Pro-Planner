from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from datetime import date, timedelta

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "data" / "dieta.db"
REPORT_DIR = ROOT / "reports"
REPORT_DIR.mkdir(exist_ok=True)

def qident(name: str) -> str:
    return '"' + str(name).replace('"', '""') + '"'

def connect():
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    return con

def tables(con):
    return [r["name"] for r in con.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    )]

def cols(con, table):
    return [dict(r) for r in con.execute(f"PRAGMA table_info({qident(table)})")]

def col_names(con, table):
    return [c["name"] for c in cols(con, table)]

def count(con, table):
    try:
        return con.execute(f"SELECT COUNT(*) AS n FROM {qident(table)}").fetchone()["n"]
    except Exception:
        return None

def count_since(con, table, date_col, days=14):
    since = (date.today() - timedelta(days=days)).isoformat()
    try:
        return con.execute(
            f"SELECT COUNT(*) AS n FROM {qident(table)} WHERE {qident(date_col)} >= ?",
            (since,)
        ).fetchone()["n"]
    except Exception:
        return None

def sample(con, sql, params=(), limit=10):
    try:
        rows = con.execute(sql, params).fetchmany(limit)
        return [dict(r) for r in rows]
    except Exception as e:
        return [{"error": str(e)}]

def find_broken_text(con, table, limit=20):
    out = []
    for c in cols(con, table):
        name = c["name"]
        typ = str(c["type"] or "").upper()
        if "TEXT" not in typ and typ != "":
            continue

        sql = (
            f"SELECT rowid AS _rid, {qident(name)} AS _val "
            f"FROM {qident(table)} "
            f"WHERE CAST({qident(name)} AS TEXT) LIKE '%?%' "
            f"LIMIT ?"
        )

        try:
            rows = con.execute(sql, (limit,)).fetchall()
        except Exception:
            continue

        for r in rows:
            out.append({
                "table": table,
                "column": name,
                "rowid": r["_rid"],
                "value": r["_val"],
            })

    return out[:limit]

def audit_foods(con, table_list):
    if "foods" not in table_list:
        return {"exists": False}

    c = col_names(con, "foods")
    report = {"exists": True, "count": count(con, "foods"), "columns": c}

    macro_cols = [x for x in ["kcal", "protein", "carbs", "fat", "sugar", "salt"] if x in c]
    if macro_cols:
        where = " OR ".join([f"{qident(x)} IS NULL" for x in macro_cols])
        report["missing_macro_samples"] = sample(
            con,
            f"SELECT * FROM {qident('foods')} WHERE {where} LIMIT 10"
        )
    else:
        report["missing_macro_samples"] = []

    text_cols = [x for x in ["name", "brand", "source_note", "notes"] if x in c]
    if text_cols:
        parts = []
        for x in text_cols:
            q = qident(x)
            parts.append(f"LOWER(COALESCE({q},'')) LIKE '%estim%'")
            parts.append(f"LOWER(COALESCE({q},'')) LIKE '%casero%'")
            parts.append(f"LOWER(COALESCE({q},'')) LIKE '%mezclad%'")
        where = " OR ".join(parts)
        report["estimated_samples"] = sample(
            con,
            f"SELECT * FROM {qident('foods')} WHERE {where} LIMIT 15"
        )
    else:
        report["estimated_samples"] = []

    return report

def audit_daily(con, table_list):
    out = {}

    for table in ["meals", "workouts", "weights"]:
        if table not in table_list:
            out[table] = {"exists": False}
            continue

        c = col_names(con, table)
        date_col = "date" if "date" in c else None

        order_col = "rowid"
        out[table] = {
            "exists": True,
            "count": count(con, table),
            "columns": c,
            "last_14_days": count_since(con, table, date_col, 14) if date_col else None,
            "recent_samples": sample(con, f"SELECT * FROM {qident(table)} ORDER BY {order_col} DESC LIMIT 5"),
        }

    return out

def audit_text(con, table_list):
    out = []
    for table in table_list:
        out.extend(find_broken_text(con, table, 10))
    return out[:80]

def main():
    if not DB.exists():
        raise SystemExit(f"DB not found: {DB}")

    con = connect()
    table_list = tables(con)

    result = {
        "db": str(DB),
        "tables": {
            t: {
                "count": count(con, t),
                "columns": col_names(con, t),
            }
            for t in table_list
        },
        "foods": audit_foods(con, table_list),
        "daily": audit_daily(con, table_list),
        "broken_text_samples": audit_text(con, table_list),
    }

    json_path = REPORT_DIR / "food_intel_audit.json"
    md_path = REPORT_DIR / "food_intel_audit.md"

    json_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = []
    lines.append("# Food Intelligence Audit")
    lines.append("")
    lines.append(f"Database: `{DB}`")
    lines.append("")
    lines.append("## Tables")
    lines.append("")
    for name, meta in result["tables"].items():
        lines.append(f"- `{name}`: {meta['count']} rows")
    lines.append("")
    lines.append("## Foods")
    lines.append("")
    foods = result["foods"]
    lines.append(f"- Exists: {foods.get('exists')}")
    lines.append(f"- Count: {foods.get('count')}")
    lines.append(f"- Columns: {', '.join(foods.get('columns', []))}")
    lines.append("")
    lines.append("### Estimated or composite food samples")
    lines.append("")
    est = foods.get("estimated_samples", [])
    if est:
        for row in est[:15]:
            name = row.get("name") or row.get("food_name") or str(row.get("id", row.get("rowid", "")))
            lines.append(f"- {name}")
    else:
        lines.append("- None detected.")
    lines.append("")
    lines.append("### Missing macro samples")
    lines.append("")
    missing = foods.get("missing_macro_samples", [])
    if missing:
        for row in missing[:15]:
            name = row.get("name") or row.get("food_name") or str(row.get("id", row.get("rowid", "")))
            lines.append(f"- {name}")
    else:
        lines.append("- None detected.")
    lines.append("")
    lines.append("## Daily data")
    lines.append("")
    for table, meta in result["daily"].items():
        lines.append(f"- `{table}`: exists={meta.get('exists')} count={meta.get('count')} last_14_days={meta.get('last_14_days')}")
    lines.append("")
    lines.append("## Broken text samples")
    lines.append("")
    broken = result["broken_text_samples"]
    if broken:
        for x in broken[:30]:
            lines.append(f"- {x['table']}.{x['column']} rowid={x['rowid']}: {x['value']}")
    else:
        lines.append("- No broken '?' text samples found.")
    lines.append("")
    lines.append("## Next implementation")
    lines.append("")
    lines.append("1. Add derived food confidence scoring.")
    lines.append("2. Add local source cache tables.")
    lines.append("3. Implement `/api/food-intel/day` without changing UI.")
    lines.append("4. Add tests for daily score and confidence.")
    lines.append("5. Add UI only after endpoint is stable.")

    md_path.write_text("\n".join(lines), encoding="utf-8")

    print(f"Wrote {json_path}")
    print(f"Wrote {md_path}")
    print()
    print(md_path.read_text(encoding="utf-8"))

if __name__ == "__main__":
    main()
