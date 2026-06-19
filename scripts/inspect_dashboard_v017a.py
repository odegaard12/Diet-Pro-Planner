from pathlib import Path

TARGETS = [
    "Inteligencia del día",
    "Qué hacer ahora",
    "Sugerir comida",
    "Foto corporal",
    "Composición corporal",
    "Peso oficial",
    "Comidas registradas",
    "Actividad",
    "Base insuficiente",
    "Confianza exacta",
]

FILES = [
    Path("static/app.js"),
    Path("static/styles.css"),
    Path("static/index.html"),
    Path("templates/index.html"),
    Path("index.html"),
]

def show_context(path, needle, lines=3):
    txt = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    hits = []
    for i, line in enumerate(txt, start=1):
        if needle.lower() in line.lower():
            start = max(1, i-lines)
            end = min(len(txt), i+lines)
            hits.append((i, start, end, txt[start-1:end]))
    return hits

print("# Dashboard v0.0.17a inspection")
for p in FILES:
    if not p.exists():
        continue
    print()
    print("=" * 80)
    print(p)
    print("=" * 80)
    print("lines:", sum(1 for _ in p.open(encoding="utf-8", errors="ignore")))

    for needle in TARGETS:
        hits = show_context(p, needle)
        if hits:
            print()
            print(f"## {needle} — {len(hits)} hits")
            for i, start, end, block in hits[:5]:
                print(f"-- hit line {i}, context {start}-{end}")
                for n, line in enumerate(block, start=start):
                    print(f"{n}: {line[:220]}")
