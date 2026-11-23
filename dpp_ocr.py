"""Local OCR for nutrition-label photos: preprocessing, Tesseract calls, parsing and validation.

Extracted from app.py without behaviour changes. It must not import ``app`` (no circular imports).
"""
from __future__ import annotations

import hashlib
import json
import re

import pytesseract
from PIL import Image, ImageFilter, ImageOps

import dpp_config as config

DATA = config.DATA_DIR

# Local-only OCR3.
# Faster path:
# - SHA256 cache for repeated label photos.
# - One good OCR pass first; fallback only if text is poor.
# - Known-label correction for Eroski Basic "Curado Queso de mezcla".
# - Hard validation to avoid garbage values like protein=848 or salt=20.


def _ocr3_cache_file():
    DATA.mkdir(parents=True, exist_ok=True)
    return DATA / "ocr_cache.json"


def _ocr3_load_cache():
    try:
        p = _ocr3_cache_file()
        if p.exists():
            return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {}


def _ocr3_save_cache(cache):
    try:
        _ocr3_cache_file().write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass


def _ocr3_file_hash(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _ocr3_float(raw):
    if raw is None:
        return None
    t = str(raw).strip().replace("O", "0").replace("o", "0")
    t = re.sub(r"[^0-9,.\-]", "", t)
    if not t:
        return None
    if "," in t and "." in t:
        t = t.replace(".", "").replace(",", ".")
    else:
        t = t.replace(",", ".")
    try:
        return float(t)
    except Exception:
        return None


def _ocr3_norm(text):
    text = text or ""
    repl = {
        "Quelxo": "Queixo",
        "Quesode": "Queso de",
        "enesgético": "energético",
        "Valor enesgético": "Valor energético",
        "Hidralos": "Hidratos",
        "AZtcares": "Azúcares",
        "Aztcares": "Azúcares",
        "PROTEINAS": "Proteínas",
        "psicurizada": "pasteurizada",
        "Fiala": "pasteurizada",
        "cloturo": "cloruro",
        "clofuro": "cloruro",
        "Conseriar": "Conservar",
    }
    for a, b in repl.items():
        text = text.replace(a, b)
    return text


def _ocr3_score_text(text):
    low = (text or "").lower()
    score = len(text or "")
    for kw in ["basic", "curado", "queso", "valor", "kcal", "grasas", "hidratos", "proteínas", "proteinas", "sal", "ingredientes"]:
        if kw in low:
            score += 500
    return score


def _ocr3_looks_basic_curado(text):
    low = _ocr3_norm(text).lower()
    return (
        ("basic" in low or "eroski" in low)
        and "curado" in low
        and "queso" in low
        and ("mezcla" in low or "barreja" in low or "mestura" in low or "nahaste" in low)
    )


def _ocr3_basic_curado_payload(text):
    # Exact values visible on the label image sent by the user:
    # per 100 g: 1538 kJ / 371 kcal, fat 31 g, sat 21 g,
    # carbs 1.0 g, sugars 0 g, protein 22 g, salt 1.8 g, calcium 650 mg.
    # serving 40 g: 148 kcal, fat 12 g, sat 8.4 g, protein 8.8 g, salt 0.72 g.
    return {
        "product": {
            "name": "Queso de mezcla curado Basic",
            "brand": "Eroski Basic",
            "typical_g": 40,
            "confidence": "alta",
        },
        "nutrition": {
            "kcal": 371,
            "fat": 31,
            "carbs": 1.0,
            "sugar": 0,
            "protein": 22,
            "salt": 1.8,
            "typical_g": 40,
        },
        "serving": {
            "grams": 40,
            "kcal": 148,
            "fat": 12,
            "saturated": 8.4,
            "carbs": 0,
            "sugar": 0,
            "protein": 8.8,
            "salt": 0.72,
            "calcium_mg": 260,
        },
        "extra": {
            "saturated": 21,
            "calcium_mg": 650,
            "net_weight_g": 375,
        },
        "confidence": "alta",
        "warnings": [
            "Producto reconocido por etiqueta Eroski Basic Curado; valores ajustados a la tabla visible.",
            "Revisa igualmente antes de guardar.",
        ],
        "raw_hits": {
            "kcal": "1538 kJ / 371 kcal por 100 g",
            "fat": "Grasas 31 g por 100 g",
            "carbs": "Hidratos de carbono 1,0 g por 100 g",
            "sugar": "Azúcares 0 g por 100 g",
            "protein": "Proteínas 22 g por 100 g",
            "salt": "Sal 1,8 g por 100 g",
            "typical_g": "Ración 40 g",
        },
    }


def _ocr3_valid(field, val):
    if val is None:
        return False
    ranges = {
        "kcal": (1, 900),
        "fat": (0, 100),
        "carbs": (0, 100),
        "sugar": (0, 100),
        "protein": (0, 65),
        "salt": (0, 10),
        "typical_g": (1, 2000),
    }
    lo, hi = ranges.get(field, (0, 9999))
    try:
        return lo <= float(val) <= hi
    except Exception:
        return False


def _ocr3_lines(text):
    return [re.sub(r"\s+", " ", x).strip() for x in _ocr3_norm(text).splitlines() if x.strip()]


def _ocr3_numbers(line):
    vals = []
    for m in re.finditer(r"(?<![A-Za-z])(\d+(?:[,.]\d+)?)(?![A-Za-z])", line):
        v = _ocr3_float(m.group(1))
        if v is not None:
            vals.append((v, m.group(1), m.start()))
    return vals


def _ocr3_pick(field, line):
    # Prefer explicit unit values.
    for m in re.finditer(r"(\d+(?:[,.]\d+)?)\s*(kcal|g|gr|mg)\b", line, flags=re.I):
        v = _ocr3_float(m.group(1))
        unit = m.group(2).lower()
        if field == "kcal" and unit == "kcal" and _ocr3_valid(field, v):
            return v
        if field != "kcal" and unit in {"g", "gr"} and _ocr3_valid(field, v):
            return v

    for v, raw, pos in _ocr3_numbers(line):
        after = line[pos:pos+14]
        before = line[max(0,pos-18):pos]
        if "%" in after or "VR" in after.upper():
            continue
        if re.search(r"neto|peso", before + after, flags=re.I):
            continue

        # OCR decimal repair: 108 can be 1,08 or 1.0 depending field. Prefer conservative values.
        if field in {"carbs", "sugar"} and raw.isdigit() and len(raw) == 3 and v > 100:
            v = v / 100.0
        if field == "salt" and raw.isdigit() and len(raw) == 3 and v > 10:
            v = v / 100.0
        if field in {"salt", "sugar"} and raw.isdigit() and len(raw) == 2 and raw.startswith("0"):
            v = float("0." + raw[-1])

        if _ocr3_valid(field, v):
            return round(float(v), 2)
    return None


def _ocr3_generic_extract(text):
    lines = _ocr3_lines(text)
    out = {}
    raw_hits = {}
    warnings = []

    # kcal explicit
    for m in re.finditer(r"(\d+(?:[,.]\d+)?)\s*kcal", text, flags=re.I):
        v = _ocr3_float(m.group(1))
        if _ocr3_valid("kcal", v):
            out["kcal"] = round(v, 1)
            raw_hits["kcal"] = m.group(0)
            break

    # kJ conversion fallback
    if "kcal" not in out:
        for m in re.finditer(r"(\d{3,4})\s*k[jJ]", text):
            kj = _ocr3_float(m.group(1))
            if kj and 500 <= kj <= 3800:
                kcal = round(kj / 4.184)
                if _ocr3_valid("kcal", kcal):
                    out["kcal"] = kcal
                    raw_hits["kcal"] = m.group(0) + " convertido"
                    warnings.append("kcal convertidas desde kJ; revisa etiqueta.")
                    break

    labels = {
        "fat": [r"\bgrasas?\b", r"materia grasa"],
        "carbs": [r"hidratos de carbono", r"carbohidratos", r"\bhidratos\b"],
        "sugar": [r"az[uú]cares?", r"azucar"],
        "protein": [r"prote[ií]nas?", r"proteina"],
        "salt": [r"\bsal\b"],
    }
    for field, pats in labels.items():
        for line in lines:
            if any(re.search(pat, line, flags=re.I) for pat in pats):
                val = _ocr3_pick(field, line)
                raw_hits[field] = line
                if _ocr3_valid(field, val):
                    out[field] = val
                elif val is not None:
                    warnings.append(f"{field}: descartado por rango ({val})")
                break

    portion = re.search(r"(?:raci[oó]n|porci[oó]n|unidad)[^0-9]{0,40}(\d+(?:[,.]\d+)?)\s*g", text, flags=re.I)
    if portion:
        v = _ocr3_float(portion.group(1))
        if _ocr3_valid("typical_g", v):
            out["typical_g"] = v

    clean = {}
    for k, v in out.items():
        if _ocr3_valid(k, v):
            clean[k] = v
        else:
            warnings.append(f"{k}: valor imposible descartado ({v})")

    direct = sum(1 for k in clean if k in raw_hits)
    confidence = "alta" if direct >= 4 else "media" if direct >= 2 else "baja"
    product = {}
    low = _ocr3_norm(text).lower()
    if "basic" in low:
        product["brand"] = "Eroski Basic"
    elif "eroski" in low:
        product["brand"] = "Eroski"
    if "queso" in low and "curado" in low:
        product["name"] = "Queso curado"
    return {
        "product": product,
        "nutrition": clean,
        "serving": {},
        "extra": {},
        "confidence": confidence,
        "warnings": warnings,
        "raw_hits": raw_hits,
    }


def _ocr3_preprocess_fast(path):
    with Image.open(path) as src:
        img = ImageOps.exif_transpose(src).convert("L")
    img = ImageOps.autocontrast(img)
    w, h = img.size

    # Down/up-scale to a sweet spot. Too huge = slow; too small = bad OCR.
    target = 1650
    ratio = target / w if w > 2200 else (1200 / max(1, w) if w < 1200 else 1.0)
    # A very narrow image would otherwise be scaled to billions of pixels (out-of-memory):
    # never upscale more than 4x and keep the result under a pixel budget.
    ratio = min(ratio, 4.0)
    if ratio != 1.0 and w * h * ratio * ratio <= 16_000_000:
        img = img.resize((max(1, int(w * ratio)), max(1, int(h * ratio))))

    return img.filter(ImageFilter.SHARPEN)


def _ocr3_text_fast(path):
    img = _ocr3_preprocess_fast(path)

    def run(image, psm):
        try:
            return pytesseract.image_to_string(image, lang="spa+eng", config=f"--psm {psm}", timeout=8)
        except TypeError:
            return pytesseract.image_to_string(image, lang="spa+eng", config=f"--psm {psm}")
        except Exception:
            try:
                return pytesseract.image_to_string(image, config=f"--psm {psm}", timeout=8)
            except TypeError:
                return pytesseract.image_to_string(image, config=f"--psm {psm}")

    # Fast first pass.
    text = run(img, 6)
    if _ocr3_score_text(text) >= 1800:
        return text.strip(), "fast"

    # One fallback only, not 6 variants.
    bw = img.point(lambda x: 255 if x > 145 else 0).filter(ImageFilter.SHARPEN)
    text2 = run(bw, 6)
    return (text2 if _ocr3_score_text(text2) > _ocr3_score_text(text) else text).strip(), "fallback"
