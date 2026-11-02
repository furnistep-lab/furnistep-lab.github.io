#!/usr/bin/env python3
"""Build the FurniStep website (GitHub Pages serves the generated files from the repo root).

    python3 tools/build.py           # regenerate every page
    python3 tools/build.py --check   # exit 1 if a generated file is out of date (nothing written)

Sources: data/guides/*.json (one per guide, from tools/import_guide.py) and src/pages/*.html (static pages; the
first line is a JSON comment with title, description and output path). Standard library only.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import re
import sys
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SITE = "https://furnistep-lab.github.io"
YOUTUBE = "https://www.youtube.com/@FurniStep"
SUBSCRIBE = YOUTUBE + "?sub_confirmation=1"
EMAIL = "furnistep@gmail.com"
YEAR = 2026
CSS_VERSION = "4"  # bump when assets/site.css or assets/site.js change, so browsers fetch the new file

NAV = [("/guides/", "Guides"), ("/request/", "Request a guide"), ("/about/", "About")]

ICONS = {
    "box": '<path d="M3 7.5 12 3l9 4.5v9L12 21l-9-4.5z"/><path d="M3 7.5 12 12l9-4.5M12 12v9"/>',
    "tools": '<path d="M14.7 6.3a4 4 0 0 0-5.4 5.1L3 17.7 6.3 21l6.3-6.3a4 4 0 0 0 5.1-5.4l-2.5 2.5-2.6-.6-.6-2.6z"/>',
    "steps": '<path d="M4 20h5v-5h5v-5h5V5"/><circle cx="19" cy="5" r="1.5"/>',
    "mute": '<path d="M11 5 6 9H3v6h3l5 4z"/><path d="m16 9 5 6M21 9l-5 6"/>',
    "cube": '<path d="M12 2 3 7v10l9 5 9-5V7z"/><path d="m3 7 9 5 9-5M12 12v10"/>',
    "check": '<circle cx="12" cy="12" r="9"/><path d="m8 12 3 3 5-6"/>',
    "calendar": '<rect x="3" y="5" width="18" height="16" rx="2"/><path d="M3 10h18M8 3v4M16 3v4"/>',
    "play": '<path d="M8 5v14l11-7z" fill="currentColor" stroke="none"/>',
    "alert": '<path d="M12 3 2 21h20z"/><path d="M12 10v5M12 18h.01"/>',
    "info": '<circle cx="12" cy="12" r="9"/><path d="M12 11v6M12 7.5h.01"/>',
    "mail": '<rect x="3" y="5" width="18" height="14" rx="2"/><path d="m3 7 9 6 9-6"/>',
    "chat": '<path d="M4 5h16v11H9l-5 4z"/>',
    "rotate": '<path d="M21 12a9 9 0 1 1-3-6.7"/><path d="M21 4v5h-5"/>',
    "music": '<path d="M9 18V5l11-2v13"/><circle cx="6" cy="18" r="3"/><circle cx="17" cy="16" r="3"/>',
}


def icon(name: str, cls: str = "ic") -> str:
    return (
        f'<svg class="{cls}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" '
        f'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">{ICONS[name]}</svg>'
    )


def e(s) -> str:
    return escape(str(s), quote=True)


# ---------------------------------------------------------------------------------------------------------- layout


def layout(path: str, title: str, description: str, body: str, *, extra_head: str = "", og_image: str = "") -> str:
    """path: the page's URL path ('/', '/guides/', '/privacy.html')."""
    full_title = title if title.startswith("FurniStep") else f"{title} · FurniStep"
    nav = "".join(
        f'<a href="{href}"{" aria-current=\"page\"" if path.startswith(href) else ""}>{label}</a>'
        for href, label in NAV
    )
    og_img = og_image or "/assets/img/og.png"
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{e(full_title)}</title>
<meta name="description" content="{e(description)}">
<link rel="canonical" href="{SITE}{path}">
<meta property="og:type" content="website">
<meta property="og:site_name" content="FurniStep">
<meta property="og:title" content="{e(full_title)}">
<meta property="og:description" content="{e(description)}">
<meta property="og:url" content="{SITE}{path}">
<meta property="og:image" content="{SITE}{og_img}">
<meta name="twitter:card" content="summary_large_image">
<meta name="theme-color" content="#FCDC19">
<link rel="icon" href="/logo.png">
<link rel="stylesheet" href="/assets/site.css?v={CSS_VERSION}">
{extra_head}</head>
<body>
<a class="skip" href="#main">Skip to content</a>
<header class="site-header">
 <div class="wrap bar">
  <a class="brand" href="/"><img src="/logo.png" alt="" width="40" height="40"><span>FURNISTEP</span></a>
  <nav class="nav" aria-label="Main">{nav}<a class="btn btn-sm btn-navy" href="{SUBSCRIBE}">Subscribe</a></nav>
 </div>
</header>
<main id="main">
{body}
</main>
<footer class="site-footer">
 <div class="wrap foot">
  <div class="foot-brand">
   <a class="brand" href="/"><img src="/logo.png" alt="" width="32" height="32"><span>FURNISTEP</span></a>
   <p>Calm 3D furniture assembly guides. No talking, just clear steps and relaxing music.</p>
  </div>
  <nav class="foot-links" aria-label="Footer">
   <a href="/guides/">Guides</a><a href="/request/">Request a guide</a><a href="/about/">About</a>
   <a href="{YOUTUBE}">YouTube</a><a href="mailto:{EMAIL}">{EMAIL}</a>
   <a href="/privacy.html">Privacy policy</a><a href="/terms.html">Terms</a>
  </nav>
 </div>
 <div class="wrap fine">© {YEAR} FurniStep. FurniStep is an independent channel and is not affiliated with, sponsored
 by, or endorsed by any furniture brand. Brand and product names are trademarks of their respective owners.</div>
</footer>
<script src="/assets/site.js?v={CSS_VERSION}" defer></script>
</body>
</html>
"""


# ---------------------------------------------------------------------------------------------------------- guides


def load_guides() -> list[dict]:
    guides = [json.loads(p.read_text(encoding="utf-8")) for p in sorted((ROOT / "data" / "guides").glob("*.json"))]
    # newest video first (publish_at, else published), then guides without a date by name
    guides.sort(key=lambda g: (when(g), g["family"]), reverse=True)
    guides.sort(key=lambda g: not when(g))
    return guides


def when(g: dict) -> str:
    """The video's publish moment as an RFC 3339 string ('' if unknown). publish_at wins over the plain date."""
    if g.get("publish_at"):
        return g["publish_at"]
    return f"{g['published']}T00:00:00Z" if g.get("published") else ""


def parse_when(s: str) -> dt.datetime:
    return dt.datetime.fromisoformat(s.replace("Z", "+00:00"))


def fmt_slot(s: str) -> str:
    """'2026-11-03T15:00:00Z' -> 'Tuesday 3 November, 15:00 UTC' (the time in the visitor's zone is added by JS)."""
    d = parse_when(s).astimezone(dt.timezone.utc)
    return f"{d.strftime('%A')} {d.day} {d.strftime('%B')}, {d.strftime('%H:%M')} UTC"


def fmt_short(s: str) -> str:
    d = parse_when(s).astimezone(dt.timezone.utc)
    return f"{d.strftime('%a')} {d.day} {d.strftime('%b')}"


def live_attr(g: dict) -> str:
    """data-live-at: JS switches the element to its live state from this moment (no rebuild needed)."""
    return f' data-live-at="{e(g["publish_at"])}"' if g.get("publish_at") else ""


def guide_url(g: dict) -> str:
    return f"/guides/{g['slug']}/"


def guide_name(g: dict) -> str:
    return f"{g['brand']} {g['family']} {g['type']}"


def fmt_time(s: float) -> str:
    total = int(s + 1e-6)
    m, sec = divmod(total, 60)
    return f"{m}:{sec:02d}"


def fmt_date(iso: str) -> str:
    d = dt.date.fromisoformat(iso)
    return f"{d.day} {d.strftime('%B %Y')}"


def guide_card(g: dict) -> str:
    out_now = f"{fmt_time(g['duration_s'])} video" if g.get("duration_s") else "Video"
    if g.get("publish_at"):  # scheduled: the date until it is out, then the same tag as a published video
        status = (
            f'<span class="tag tag-soon" data-live-at="{e(g["publish_at"])}" data-live-text="{e(out_now)}">'
            f"Out {fmt_short(g['publish_at'])}</span>"
        )
    elif g.get("youtube_id"):
        status = f'<span class="tag tag-ok">{out_now}</span>'
    else:
        status = '<span class="tag">Coming soon</span>'
    img = (
        f'<img src="/{e(g["image"])}" alt="{e(guide_name(g))}" width="640" height="360" loading="lazy">'
        if g.get("image")
        else '<div class="card-ph"></div>'
    )
    search = " ".join([g["brand"], g["family"], g["type"], g["category"], g["dims_cm"], *g.get("skus", [])]).lower()
    return f"""<a class="card guide-card" href="{guide_url(g)}" data-brand="{e(g["brand"])}" data-category="{e(g["category"])}" data-search="{e(search)}">
 <div class="card-img">{img}{status}</div>
 <div class="card-body">
  <div class="eyebrow">{e(g["brand"])} · {e(g["category"])}</div>
  <h3>{e(g["family"])} {e(g["type"])}</h3>
  <p class="muted">{e(g["dims_cm"])} cm · {e(g["color"])} · {len(g["steps"])} steps</p>
 </div>
</a>"""


def video_block(g: dict) -> str:
    name = guide_name(g)
    if g.get("youtube_id"):
        vid = e(g["youtube_id"])
        poster = f"https://i.ytimg.com/vi/{vid}/hqdefault.jpg"
        poster = f"/{e(g['image'])}" if g.get("image") else poster
        premiere = ""
        if g.get("publish_at"):  # private until its slot: the player stays off until then (site.js)
            btn3d = (
                f'<a class="btn btn-yellow" href="{viewer_url(g)}">{icon("cube", "ic-xs")} See it in 3D now</a>'
                if g.get("model3d")
                else ""
            )
            sub_cls = "btn-ghost-light" if g.get("model3d") else "btn-yellow"
            premiere = f"""<div class="premiere"><strong>Video out {e(fmt_slot(g["publish_at"]))}</strong>
 <span class="local-time" data-at="{e(g["publish_at"])}"></span>
 <div class="actions center">{btn3d}<a class="btn {sub_cls}" href="{SUBSCRIBE}">Subscribe to get notified</a></div></div>"""
        return f"""<div class="video" data-yt="{vid}" data-title="{e(name)} assembly"{live_attr(g)}>
 <img src="{poster}" alt="" width="1280" height="720">
 <button class="play" type="button" aria-label="Play the {e(name)} assembly video">{icon("play", "ic-play")}</button>{premiere}
 <p class="video-note">The video plays from YouTube (privacy-enhanced mode) when you press play.
 <a href="https://www.youtube.com/watch?v={vid}">Watch on YouTube</a></p>
</div>"""
    if g.get("publish_at"):
        soon = f"""<strong>Video out {e(fmt_slot(g["publish_at"]))}</strong>
 <span class="local-time" data-at="{e(g["publish_at"])}"></span>"""
    else:
        soon = """<strong>Video coming soon</strong>
 <span>New guides go live every Tuesday, Thursday and Saturday at 15:00 UTC.</span>"""
    return f"""<div class="video video-soon">
 <div class="soon-over">{soon}
 <div class="actions center">{f'<a class="btn btn-yellow" href="{viewer_url(g)}">{icon("cube", "ic-xs")} See it in 3D now</a>' if g.get("model3d") else ""}
 <a class="btn {"btn-ghost-light" if g.get("model3d") else "btn-yellow"}" href="{SUBSCRIBE}">Subscribe to get notified</a></div></div>
</div>"""


def item_list(items: list[dict], with_qty: bool) -> str:
    rows = []
    for it in items:
        qty = f'<span class="qty">{it["qty"]}×</span>' if with_qty else ""
        if "included" in it and not with_qty:
            tag = '<span class="tag tag-ok">In the box</span>' if it["included"] else ""
        else:
            tag = '<span class="tag tag-warn">Not included</span>' if it.get("included") is False else ""
        rows.append(f"<li>{qty}<span>{e(it['label'])}</span>{tag}</li>")
    return '<ul class="items">' + "".join(rows) + "</ul>"


def guide_page(g: dict, guides: list[dict]) -> str:
    name = guide_name(g)
    url = guide_url(g)
    has_video = bool(g.get("youtube_id"))
    title = f"How to assemble the {name} ({g['dims_cm']} cm)"
    desc = (
        f"Calm 3D step-by-step assembly guide for the {name} ({g['dims_cm']} cm, {g['color'].lower()}): "
        f"tools you need, what's in the box and all {len(g['steps'])} steps. No talking."
    )

    steps_html = []
    for s in g["steps"]:
        head = s["title"] or s["text"]
        body = f"<p>{e(s['text'])}</p>" if s["title"] else ""
        chips = "".join(f'<span class="chip">{icon("tools", "ic-xs")}{e(t)}</span>' for t in s["tools"])
        chips = f'<div class="chips">{chips}</div>' if chips else ""
        warn = (
            f'<div class="callout callout-warn">{icon("alert")}<p><strong>Safety:</strong> {e(s["warning"])}</p></div>'
            if s.get("warning")
            else ""
        )
        note = (
            f'<div class="callout callout-info">{icon("info")}<p><strong>Note:</strong> {e(s["note"])}</p></div>'
            if s.get("note")
            else ""
        )
        seek = ""
        if has_video and s.get("start_s") is not None:
            t = int(s["start_s"])
            wait = " seek-wait" if g.get("publish_at") else ""  # shown once the video is out (site.js)
            seek = (
                f'<a class="seek{wait}" href="https://www.youtube.com/watch?v={e(g["youtube_id"])}&amp;t={t}s" '
                f'data-seek="{t}">{icon("play", "ic-xs")}{fmt_time(s["start_s"])}</a>'
            )
        if g.get("model3d"):
            seek += (
                f'<a class="seek seek-3d" href="{viewer_url(g)}#step-{s["n"]}">{icon("cube", "ic-xs")}'
                f'<span>3D<span class="sr"> view of step {s["n"]}</span></span></a>'
            )
        steps_html.append(
            f"""<li class="step" id="step-{s["n"]}">
 <div class="step-n" aria-hidden="true">{s["n"]}</div>
 <div class="step-body"><h3><span class="sr">Step {s["n"]}: </span>{e(head)}</h3>{body}{chips}{warn}{note}</div>
 <div class="step-links">{seek}</div>
</li>"""
        )

    meta = [g["color"]]
    if g.get("skus"):
        meta.append("Article " + ", ".join(g["skus"]))
    meta.append(f"{len(g['steps'])} steps")
    if g.get("duration_s"):
        meta.append(f"{fmt_time(g['duration_s'])} video")
    if g.get("publish_at"):
        meta.append(f"Video {fmt_date(g['publish_at'][:10])}")
    elif g.get("published"):
        meta.append(f"Published {fmt_date(g['published'])}")
    meta_html = "".join(f"<li>{e(m)}</li>" for m in meta)

    related = [x for x in guides if x["slug"] != g["slug"] and x["category"] == g["category"]][:3]
    if len(related) < 3:
        related += [x for x in guides if x["slug"] != g["slug"] and x not in related][: 3 - len(related)]
    related_html = (
        f"""<section class="section"><div class="wrap"><h2>More guides</h2>
<div class="grid">{"".join(guide_card(x) for x in related)}</div></div></section>"""
        if related
        else ""
    )

    howto = {
        "@context": "https://schema.org",
        "@type": "HowTo",
        "name": title,
        "description": desc,
        "image": f"{SITE}/{g['image']}" if g.get("image") else None,
        "tool": [{"@type": "HowToTool", "name": t["label"]} for t in g["tools"]],
        "supply": [{"@type": "HowToSupply", "name": h["label"]} for h in g["hardware"]],
        "step": [
            {
                "@type": "HowToStep",
                "position": s["n"],
                "name": s["title"] or s["text"],
                "text": s["text"],
                "url": f"{SITE}{url}#step-{s['n']}",
            }
            for s in g["steps"]
        ],
    }
    ld = [howto]
    if has_video and when(g):
        video = {
            "@context": "https://schema.org",
            "@type": "VideoObject",
            "name": title,
            "description": desc,
            "thumbnailUrl": [f"https://i.ytimg.com/vi/{g['youtube_id']}/maxresdefault.jpg"],
            "uploadDate": g.get("publish_at") or g["published"],
            "embedUrl": f"https://www.youtube-nocookie.com/embed/{g['youtube_id']}",
            "contentUrl": f"https://www.youtube.com/watch?v={g['youtube_id']}",
        }
        if g.get("duration_s"):
            m, s = divmod(int(g["duration_s"]), 60)
            video["duration"] = f"PT{m}M{s}S"
        clips = clip_parts(g)
        if clips:
            video["hasPart"] = clips
        ld.append(video)
    ld_html = "".join(
        '<script type="application/ld+json">'
        + json.dumps({k: v for k, v in x.items() if v is not None}, ensure_ascii=False).replace("</", "<\\/")
        + "</script>\n"
        for x in ld
    )

    body = f"""<section class="guide-head"><div class="wrap">
<nav class="crumbs" aria-label="Breadcrumb"><a href="/guides/">Guides</a> / <span>{e(g["brand"])}</span> / <span>{e(g["family"])} {e(g["type"])}</span></nav>
<h1>How to assemble the {e(name)} <span class="h1-dims">{e(g["dims_cm"])} cm</span></h1>
<ul class="meta">{meta_html}</ul>
{video_block(g)}
{teaser_3d(g)}
</div></section>

<section class="section"><div class="wrap two">
 <div class="panel"><h2>{icon("tools")} Tools you need</h2>{item_list(g["tools"], with_qty=False)}</div>
 <div class="panel"><h2>{icon("box")} What's in the box</h2>
  <h3 class="sub">Parts</h3>{item_list(g["parts"], with_qty=True)}
  <h3 class="sub">Hardware</h3>{item_list(g["hardware"], with_qty=True)}</div>
</div></section>

<section class="section section-soft"><div class="wrap narrow">
<h2>{icon("steps")} Step by step</h2>
<ol class="steps">{"".join(steps_html)}</ol>
<div class="callout callout-info">{icon("info")}<p>FurniStep guides are made to help you follow the assembly. They are
not the official instructions: always check the manual that comes with your product
{f"(<strong>{e(g['manual_code'])}</strong>)" if g.get("manual_code") else ""} and follow its safety warnings. This guide
is not affiliated with, sponsored by, or endorsed by {e(g["brand"])}.</p></div>
</div></section>
{related_html}"""
    og = f"/{g['image']}" if g.get("image") else ""
    return layout(url, title, desc, body, extra_head=ld_html, og_image=og)


def clip_parts(g: dict) -> list[dict]:
    """Google key moments: one schema.org Clip per step with a time in the video (merged chapters share a start, so
    a step that starts where the previous one does is folded into it)."""
    steps = [s for s in g["steps"] if s.get("start_s") is not None]
    end_all = g.get("duration_s")
    clips: list[dict] = []
    for i, s in enumerate(steps):
        start = int(s["start_s"])
        if clips and clips[-1]["startOffset"] == start:
            continue
        nxt = next((int(x["start_s"]) for x in steps[i + 1 :] if int(x["start_s"]) > start), None)
        end = nxt if nxt is not None else (int(end_all) if end_all else None)
        clip = {
            "@type": "Clip",
            "name": f"Step {s['n']}: {s['title'] or s['text']}",
            "startOffset": start,
            "url": f"https://www.youtube.com/watch?v={g['youtube_id']}&t={start}s",
        }
        if end is not None and end > start:
            clip["endOffset"] = end
        clips.append(clip)
    return clips


def viewer_url(g: dict) -> str:
    return f"/guides/{g['slug']}/3d/"


def teaser_3d(g: dict) -> str:
    if not g.get("model3d"):
        return ""
    return f"""<a class="teaser-3d" href="{viewer_url(g)}">
 <span class="teaser-3d-ic">{icon("cube")}</span>
 <span class="teaser-3d-t"><strong>New: explore this guide in 3D</strong>
 <span>Play every step, then turn, zoom and look from any side.</span></span>
 <span class="btn btn-navy btn-sm">Open 3D guide</span>
</a>"""


def viewer_page(g: dict) -> str:
    """The interactive 3D guide: the video's own assembly animation, step by step, with free orbit and zoom."""
    m = g["model3d"]
    name = guide_name(g)
    url = viewer_url(g)
    title = f"{name} ({g['dims_cm']} cm) in 3D: interactive assembly guide"
    desc = (
        f"Interactive 3D assembly guide for the {name} ({g['dims_cm']} cm): play each step, pause, "
        "turn the furniture and zoom in on every screw. Works on phones, no app needed."
    )
    steps = []
    for s in g["steps"]:
        head = s["title"] or s["text"]
        steps.append(
            f'<li><a href="#step-{s["n"]}" data-v3d-step="{s["n"]}"><span class="v3d-n">{s["n"]}</span>'
            f"<span>{e(head)}</span></a></li>"
        )
    steps.append('<li><a href="#done" data-v3d-step="done"><span class="v3d-n">✓</span><span>Finished</span></a></li>')
    tools = ", ".join(t["label"] for t in g["tools"])
    body = f"""<section class="guide-head v3d-head"><div class="wrap">
<nav class="crumbs" aria-label="Breadcrumb"><a href="/guides/">Guides</a> / <a href="{guide_url(g)}">{e(g["family"])} {e(g["type"])}</a> / <span>3D</span></nav>
<h1>{e(name)} in 3D <span class="h1-dims">{e(g["dims_cm"])} cm</span></h1>
<p class="lead">Play the assembly step by step. Drag to turn it, scroll or pinch to zoom, and press
<strong>Follow camera</strong> to go back to the guided view.</p>

<div class="v3d" data-src="/{e(m["dir"])}/" data-v="{e(m.get("version", ""))}" tabindex="-1">
 <div class="v3d-main">
  <div class="v3d-stage">
   <p class="v3d-status" role="status">Loading 3D model…</p>
   <noscript><p class="v3d-status">The 3D view needs JavaScript. <a href="{guide_url(g)}">See the written steps</a>.</p></noscript>
  </div>
  <p class="v3d-caption" aria-live="polite"></p>
  <div class="v3d-bar">
   <button type="button" class="v3d-btn v3d-prev" aria-label="Previous step"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6 5h2v14H6zM20 5v14L9 12z"/></svg></button>
   <button type="button" class="v3d-btn v3d-play" aria-label="Play"><svg class="i-play" viewBox="0 0 24 24" aria-hidden="true"><path d="M8 5v14l11-7z"/></svg><svg class="i-pause" viewBox="0 0 24 24" aria-hidden="true"><path d="M7 5h4v14H7zM13 5h4v14h-4z"/></svg></button>
   <button type="button" class="v3d-btn v3d-next" aria-label="Next step"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M16 5h2v14h-2zM4 5v14l11-7z"/></svg></button>
   <div class="v3d-track"><input class="v3d-scrub" type="range" min="0" max="1" step="0.01" value="0" aria-label="Position in the guide"><div class="v3d-ticks" aria-hidden="true"></div></div>
   <span class="v3d-time">0:00</span>
   <button type="button" class="v3d-btn v3d-speed" aria-label="Playback speed">1×</button>
   <button type="button" class="v3d-btn v3d-follow is-on" aria-pressed="true">{icon("rotate", "ic-xs")}<span>Follow camera</span></button>
   <button type="button" class="v3d-btn v3d-full" aria-label="Full screen"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 9V4h5v2H6v3zm11-5h5v5h-2V6h-3zM4 15h2v3h3v2H4zm14 0h2v5h-5v-2h3z"/></svg></button>
  </div>
 </div>
 <aside class="v3d-steps" aria-label="Steps"><h2 class="sub">Steps</h2><ol>{"".join(steps)}</ol>
 <p class="muted v3d-tools">{icon("tools", "ic-xs")} You need: {e(tools)}</p></aside>
</div>
<p class="muted v3d-keys">Keys: Space play or pause, ← → previous or next step, C follow camera.
This is our own 3D model made from the manual, not the official instructions{f" ({e(g['manual_code'])})" if g.get("manual_code") else ""}:
always follow the safety warnings in the manual that comes with your product.
<a href="{guide_url(g)}">Back to the guide</a>.</p>
</div></section>"""
    js = ROOT / "assets" / "3d" / "viewer.js"
    js_ver = hashlib.sha256(js.read_bytes()).hexdigest()[:10] if js.exists() else "0"
    head = f'<script type="module" src="/assets/3d/viewer.js?v={js_ver}"></script>\n'
    og = f"/{g['image']}" if g.get("image") else ""
    return layout(url, title, desc, body, extra_head=head, og_image=og)


def guides_index(guides: list[dict]) -> str:
    brands = sorted({g["brand"] for g in guides})
    cats = sorted({g["category"] for g in guides})

    def chips(kind: str, values: list[str]) -> str:
        out = [f'<button type="button" class="filter is-on" data-filter="{kind}" data-value="">All</button>']
        out += [f'<button type="button" class="filter" data-filter="{kind}" data-value="{e(v)}">{e(v)}</button>' for v in values]
        return "".join(out)

    cards = "".join(guide_card(g) for g in guides) or '<p class="muted">The first guides are on their way.</p>'
    body = f"""<section class="page-head"><div class="wrap">
<h1>Assembly guides</h1>
<p class="lead">Every guide shows the tools you need, what's in the box and each step, one part at a time.</p>
</div></section>
<section class="section"><div class="wrap">
<div class="filters" id="filters" hidden>
 <label class="search"><span class="sr">Search guides</span><input type="search" id="q" placeholder="Search by name, type or article number"></label>
 <div class="filter-row" role="group" aria-label="Brand">{chips("brand", brands)}</div>
 <div class="filter-row" role="group" aria-label="Type">{chips("category", cats)}</div>
</div>
<div class="grid" id="guide-grid">{cards}</div>
<p class="muted empty" id="no-results" hidden>No guides match. <a href="/request/">Request this one</a>.</p>
</div></section>
{request_band()}"""
    return layout(
        "/guides/",
        "Assembly guides",
        "All FurniStep furniture assembly guides: calm 3D step-by-step videos with tools, parts and every step.",
        body,
    )


def request_band() -> str:
    return f"""<section class="band band-navy"><div class="wrap band-in">
<div><h2>Can't find your furniture?</h2><p>Tell us what to assemble next. Requests decide what we make.</p></div>
<a class="btn btn-yellow" href="/request/">Request a guide</a>
</div></section>"""


# ------------------------------------------------------------------------------------------------------------ home


def home(guides: list[dict]) -> str:
    latest = guides[:6]
    scheduled = sorted((g for g in guides if g.get("publish_at")), key=lambda g: g["publish_at"])
    hero_g = scheduled[0] if scheduled else next((g for g in guides if g.get("youtube_id")), guides[0] if guides else None)
    feature = ""
    if hero_g:
        label = "Coming soon" if not hero_g.get("youtube_id") or hero_g.get("publish_at") else "Latest guide"
        if hero_g.get("publish_at"):
            label = f"Out {fmt_short(hero_g['publish_at'])}"
        feature = f"""<a class="hero-card" href="{guide_url(hero_g)}">
 <img src="/{e(hero_g["image"])}" alt="{e(guide_name(hero_g))}" width="1280" height="720">
 <span class="hero-card-label"><span{live_attr(hero_g)} data-live-text="New">{label}</span>: <strong>{e(hero_g["family"])} {e(hero_g["type"])}</strong></span>
</a>"""

    steps = [
        ("box", "What's in the box", "Every panel, screw and dowel laid out, so you can check the box before you start."),
        ("tools", "Tools you need", "The tools from the manual, plus anything it assumes you have, marked clearly."),
        ("steps", "Step by step", "Each step animated in 3D, one part at a time, with the step on screen."),
    ]
    how = "".join(
        f'<div class="how"><div class="how-ic">{icon(i)}</div><h3>{t}</h3><p>{d}</p></div>' for i, t, d in steps
    )
    why = [
        ("mute", "No talking", "Just calm music and clear on-screen steps. Watch with the sound off if you like."),
        ("cube", "Clear 3D views", "Close-up camera angles show exactly which part, which hole and which screw."),
        ("check", "Checked by a person", "Every guide is read from the official manual and reviewed before it goes out."),
        ("music", "Made by us", "Our own 3D models, animations and music. No manufacturer artwork."),
    ]
    why_html = "".join(
        f'<div class="why">{icon(i)}<div><h3>{t}</h3><p>{d}</p></div></div>' for i, t, d in why
    )
    grid = "".join(guide_card(g) for g in latest)
    coming = "".join(
        f"""<li{live_attr(g)}><a href="{guide_url(g)}"><span class="cu-date">{e(fmt_short(g["publish_at"]))}</span>
<span class="cu-name">{e(g["brand"])} {e(g["family"])} {e(g["type"])} <span class="muted">{e(g["dims_cm"])} cm</span></span>
<span class="tag tag-soon" data-live-at="{e(g["publish_at"])}" data-live-text="Out now">15:00 UTC</span></a></li>"""
        for g in scheduled
    )
    coming_html = f'<ol class="coming-up" aria-label="Coming up">{coming}</ol>' if coming else ""
    body = f"""<section class="hero"><div class="wrap hero-in">
 <div class="hero-text">
  <p class="eyebrow">Calm 3D assembly guides</p>
  <h1>Furniture assembly, one calm step at a time.</h1>
  <p class="lead">FurniStep turns flat-pack instructions into clear 3D animations you can follow at your own pace.
  No talking, no rushing: just the parts, the tools and each step.</p>
  <div class="actions"><a class="btn btn-navy" href="/guides/">Browse guides</a>
  <a class="btn btn-ghost" href="{SUBSCRIBE}">{icon("play", "ic-xs")} Subscribe on YouTube</a></div>
 </div>
 <div class="hero-media">{feature}</div>
</div></section>

<section class="section"><div class="wrap">
<h2 class="center">How every guide works</h2>
<div class="hows">{how}</div>
</div></section>

<section class="section section-soft"><div class="wrap">
<div class="row-head"><h2>Latest guides</h2><a href="/guides/">All guides →</a></div>
<div class="grid">{grid}</div>
</div></section>

<section class="section"><div class="wrap"><div class="schedule">
 <div class="schedule-ic">{icon("calendar")}</div>
 <div><h2>New guides every Tuesday, Thursday and Saturday</h2>
 <p>At 15:00 UTC<span id="next-slot"></span>. Subscribe on YouTube and you won't miss one.</p></div>
 <a class="btn btn-navy" href="{SUBSCRIBE}">Subscribe</a>
</div>{coming_html}</div></section>

<section class="section section-soft"><div class="wrap">
<h2 class="center">Why FurniStep</h2>
<div class="whys">{why_html}</div>
</div></section>
{request_band()}"""
    return layout(
        "/",
        "FurniStep: calm 3D furniture assembly guides",
        "FurniStep turns flat-pack furniture instructions into calm, clear 3D step-by-step videos. "
        "No talking, just clear steps and relaxing music.",
        body,
    )


# ------------------------------------------------------------------------------------------------- static + extras


def static_pages() -> dict[str, str]:
    out = {}
    for src in sorted((ROOT / "src" / "pages").glob("*.html")):
        first, rest = src.read_text(encoding="utf-8").split("\n", 1)
        m = re.fullmatch(r"<!--\s*(\{.*\})\s*-->", first.strip())
        if not m:
            raise SystemExit(f"{src}: first line must be <!-- {{json}} -->")
        meta = json.loads(m.group(1))
        body = rest.replace("{{EMAIL}}", EMAIL).replace("{{YOUTUBE}}", YOUTUBE).replace("{{SUBSCRIBE}}", SUBSCRIBE)
        out[meta["out"]] = layout(meta["path"], meta["title"], meta["description"], body)
    return out


def sitemap(paths: list[str]) -> str:
    urls = "".join(f"<url><loc>{SITE}{p}</loc></url>\n" for p in paths)
    return f'<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n{urls}</urlset>\n'


def render_all() -> dict[str, str]:
    guides = load_guides()
    files: dict[str, str] = {"index.html": home(guides), "guides/index.html": guides_index(guides)}
    for g in guides:
        files[f"guides/{g['slug']}/index.html"] = guide_page(g, guides)
        if g.get("model3d"):
            files[f"guides/{g['slug']}/3d/index.html"] = viewer_page(g)
    files.update(static_pages())
    pages = [
        "/" + (k[: -len("index.html")] if k.endswith("index.html") else k)
        for k in files
        if k != "404.html"
    ]
    files["sitemap.xml"] = sitemap(sorted(pages, key=lambda p: (p.count("/"), p)))
    files["robots.txt"] = f"User-agent: *\nAllow: /\nSitemap: {SITE}/sitemap.xml\n"
    return files


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args(argv)
    files = render_all()
    stale = []
    for rel, content in files.items():
        p = ROOT / rel
        if p.exists() and p.read_text(encoding="utf-8") == content:
            continue
        stale.append(rel)
        if not a.check:
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content, encoding="utf-8")
    # generated guide folders without a data file any more
    for d in (ROOT / "guides").glob("*/"):
        if f"guides/{d.name}/index.html" not in files:
            stale.append(f"guides/{d.name}/ (no data file)")
        elif (d / "3d").is_dir() and f"guides/{d.name}/3d/index.html" not in files:
            stale.append(f"guides/{d.name}/3d/ (no model3d in the data file)")
    if a.check:
        if stale:
            print("out of date (run python3 tools/build.py):\n  " + "\n  ".join(stale))
            return 1
        print("site is up to date")
        return 0
    print(f"{len(files)} files, {len(stale)} changed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
