#!/usr/bin/env python3
"""Turn a FurniStep Assembly Spec (ytproject catalog/<brand>/<id>/spec.json) into a guide data file.

    python3 tools/import_guide.py ../ytproject/catalog/ikea/lack-tv-bench-aa2248458/spec.json \
        --image path/to/thumbnail.jpg [--chapters out/final/chapters.json] \
        [--youtube-id VIDEO_ID --published 2026-11-03] [--category "TV benches"]

Writes data/guides/<slug>.json (and assets/img/guides/<slug>.jpg from --image). Re-running keeps fields that are
already in the file and not given again (youtube_id, published, category, image), so a guide can be imported
before its video is out and updated with the video ID later. Then run tools/build.py.

Only the English text of the spec is used: the site is in English.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GUIDES = ROOT / "data" / "guides"
IMAGES = ROOT / "assets" / "img" / "guides"

# product.name (lower case) -> category shown on the site; mirrors the playlists in ytproject brand/config.yaml.
CATEGORIES = {
    "TV benches & units": ["tv bench", "tv unit"],
    "Bookcases & shelves": ["bookcase", "shelving unit", "shelf", "wall shelf"],
    "Dressers": ["chest of drawers", "dresser"],
    "Wardrobes": ["wardrobe"],
    "Beds": ["bed frame", "bed"],
    "Desks": ["desk"],
    "Tables": ["table", "coffee table", "side table", "nightstand", "bedside table"],
    "Cabinets": ["cabinet", "shoe cabinet"],
    "Chairs & stools": ["chair", "stool"],
}


def slugify(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def category_for(name: str) -> str:
    n = name.lower()
    for cat, types in CATEGORIES.items():
        if n in types:
            return cat
    return "Other furniture"


def cm(mm: float) -> str:
    v = mm / 10
    return str(int(v)) if v == int(v) else f"{v:g}"


def strip_paren(label: str) -> str:
    """'Allen key 100092 (in the box)' -> 'Allen key 100092'; the site shows inclusion as a tag."""
    return re.sub(r"\s*\((in the box|not included)\)\s*$", "", label, flags=re.I)


def build_guide(spec: dict, chapters: dict | None) -> dict:
    p = spec["product"]
    w, d, h = (cm(x) for x in p["overall_mm"])
    dims = f"{w}x{d}x{h}"
    text = spec.get("text", {}).get("en", {})
    articles = p.get("articles", [])
    color = articles[0]["color"] if articles else ""
    slug = slugify(f"{p['brand']} {p['family']} {p['name']} {dims}")

    starts: dict[str, float] = {}
    duration = None
    if chapters:
        duration = chapters.get("duration_s")
        for c in chapters["chapters"]:
            for seg in c["segments"]:
                starts.setdefault(seg, c["start_s"])  # a merged chapter: every step in it starts at its start

    tool_labels = {t["id"]: strip_paren(t["label"]) for t in spec["tools"]}
    steps = []
    for n, s in enumerate(spec["steps"], start=1):
        steps.append(
            {
                "n": n,
                "title": text.get(f"{s['id']}.chapter") or "",
                "text": text.get(s["text_key"], ""),
                "note": text.get(s["note_key"]) if s.get("note_key") else None,
                "warning": text.get(s["warning_key"]) if s.get("warning_key") else None,
                "tools": [tool_labels[t] for t in s.get("tools", []) if t in tool_labels],
                "start_s": starts.get(s["id"]),
            }
        )

    return {
        "slug": slug,
        "assembly_id": spec["assembly_id"],
        "brand": p["brand"],
        "family": p["family"],
        "type": p["name"],
        "color": color,
        "dims_cm": dims,
        "skus": [a["sku"] for a in articles],
        "manual_code": spec.get("source", {}).get("manual_code", ""),
        "category": category_for(p["name"]),
        "youtube_id": None,
        "published": None,
        "duration_s": duration,
        "image": None,
        "parts": [{"label": x["label"], "qty": x["qty"]} for x in spec["parts"]],
        "hardware": [
            {"label": strip_paren(x["label"]), "qty": x["qty"], "included": x.get("included", True)}
            for x in spec["hardware"]
        ],
        "tools": [{"label": strip_paren(t["label"]), "included": t.get("included", False)} for t in spec["tools"]],
        "steps": steps,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("spec", type=Path)
    ap.add_argument("--chapters", type=Path, help="chapters.json from python -m pipeline.video build")
    ap.add_argument("--image", type=Path, help="card image, e.g. the video thumbnail (resized to 1280x720 JPEG)")
    ap.add_argument("--youtube-id")
    ap.add_argument("--published", help="publish date YYYY-MM-DD")
    ap.add_argument("--category")
    a = ap.parse_args(argv)

    spec = json.loads(a.spec.read_text(encoding="utf-8"))
    chapters = json.loads(a.chapters.read_text(encoding="utf-8")) if a.chapters else None
    g = build_guide(spec, chapters)

    out = GUIDES / f"{g['slug']}.json"
    old = json.loads(out.read_text(encoding="utf-8")) if out.exists() else {}
    for k in ("youtube_id", "published", "category", "image", "duration_s"):
        if old.get(k) and not g.get(k):
            g[k] = old[k]
    if not chapters and old.get("steps"):  # keep chapter times from an earlier import
        for s, o in zip(g["steps"], old["steps"]):
            if s["start_s"] is None:
                s["start_s"] = o.get("start_s")
    if a.youtube_id:
        g["youtube_id"] = a.youtube_id
    if a.published:
        g["published"] = a.published
    if a.category:
        g["category"] = a.category

    if a.image:
        from PIL import Image  # only needed for images

        IMAGES.mkdir(parents=True, exist_ok=True)
        im = Image.open(a.image).convert("RGB")
        im.thumbnail((1280, 720))
        dest = IMAGES / f"{g['slug']}.jpg"
        im.save(dest, "JPEG", quality=82, optimize=True, progressive=True)
        g["image"] = f"assets/img/guides/{dest.name}"

    GUIDES.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(g, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {out.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
