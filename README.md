# furnistep-lab.github.io

The FurniStep website, served by GitHub Pages from the root of `main`: https://furnistep-lab.github.io/

The HTML pages are generated. Edit the sources, then run `python3 tools/build.py` and commit the result
(CI runs `python3 tools/build.py --check` and fails if a generated page is out of date). Standard library only.

| Source | Generates |
|---|---|
| `data/guides/<slug>.json` | `guides/<slug>/index.html`, the guide list and the home page cards |
| `src/pages/*.html` (first line: JSON with title, description, path, output file) | `about/`, `request/`, `privacy.html`, `terms.html`, `404.html` |
| `tools/build.py` | layout, home page, `sitemap.xml`, `robots.txt` |
| `assets/site.css`, `assets/site.js` | (served as is; bump `CSS_VERSION` in `tools/build.py` after a change) |

`privacy.html` and `terms.html` are linked from the Google OAuth consent screen: keep those URLs.

## Adding a guide

From a spec in the [ytproject](https://github.com/furnistep-lab/ytproject) catalog:

```
python3 tools/import_guide.py ../ytproject/catalog/ikea/lack-tv-bench-aa2248458/spec.json \
    --image path/to/thumbnail.jpg --chapters path/to/out/chapters.json
python3 tools/build.py
```

The guide shows "Video coming soon" until it has a video. When the video is public, add its ID and date
(the other fields are kept):

```
python3 tools/import_guide.py <spec.json> --youtube-id VIDEO_ID --published 2026-11-03 --chapters chapters.json
python3 tools/build.py
```

`--chapters` (the `chapters.json` written by `python -m pipeline.video build`) gives each step its time in the
video, shown as a "play from here" link. Images need Pillow (`pip install pillow`).

## Privacy

No cookies, analytics or third-party requests on page load. The YouTube player loads only after the visitor
presses play, from youtube-nocookie.com (the privacy policy says so).
