# furnistep-lab.github.io

The FurniStep website, served by GitHub Pages from the root of `main`: https://furnistep-lab.github.io/

The HTML pages are generated. Edit the sources, then run `python3 tools/build.py` and commit the result
(CI runs `python3 tools/build.py --check` and fails if a generated page is out of date). Standard library only.

| Source | Generates |
|---|---|
| `data/guides/<slug>.json` | `guides/<slug>/index.html`, the guide list and the home page cards |
| `src/pages/*.html` (first line: JSON with title, description, path, output file) | `about/`, `request/`, `privacy.html`, `terms.html`, `404.html` |
| `tools/build.py` | layout, home page, `sitemap.xml`, `robots.txt` |
| `data/guides/<slug>.json` with `model3d` | `guides/<slug>/3d/index.html` (interactive 3D guide) |
| `assets/site.css`, `assets/site.js` | (served as is; bump `CSS_VERSION` in `tools/build.py` after a change) |
| `src/viewer3d/main.js` | `assets/3d/viewer.js` (bundled with three.js by `tools/build_viewer.sh`, committed) |

`privacy.html` and `terms.html` are linked from the Google OAuth consent screen: keep those URLs.

## Adding a guide

From a spec in the [ytproject](https://github.com/furnistep-lab/ytproject) catalog:

```
python3 tools/import_guide.py ../ytproject/catalog/ikea/lack-tv-bench-aa2248458/spec.json \
    --image path/to/thumbnail.jpg --chapters path/to/out/chapters.json
python3 tools/build.py
```

The guide shows "Video coming soon" until it has a video. As soon as the video is uploaded (still private), add its
ID and its publish slot (the other fields are kept):

```
python3 tools/import_guide.py <spec.json> --youtube-id VIDEO_ID --publish-at 2026-11-03T15:00:00Z --chapters chapters.json
python3 tools/build.py
```

Until `--publish-at` the page says "Video out <date>" (with the visitor's local time), the player and the per-step
video links stay off, and cards and the home page "coming up" list show the date. At that moment `assets/site.js`
switches everything to the live video by itself, so no rebuild is needed on publish day. `--publish-at` without
`--youtube-id` (upload not done yet) shows the date only. `--published YYYY-MM-DD` is for videos that are already
public. The VideoObject JSON-LD gets one `Clip` per step (Google key moments) from the chapter times.

`--chapters` (the `chapters.json` written by `python -m pipeline.video build`) gives each step its time in the
video, shown as a "play from here" link. Images need Pillow (`pip install pillow`).

## 3D guides

A guide can have an interactive 3D page (`/guides/<slug>/3d/`): the video's own assembly animation, step by step,
which visitors can pause, turn and zoom. The guide page links to it (a banner, the "See it in 3D now" button while
the video is not out, and a "3D" link on every step, which opens that step: `/3d/#step-3`).

Export the model from ytproject (no Blender needed) and import it:

```
(cd ../ytproject && python -m pipeline.web export catalog/ikea/lack-tv-bench-aa2248458/spec.json --out out/web)
python3 tools/import_guide.py ../ytproject/catalog/ikea/lack-tv-bench-aa2248458/spec.json --model3d ../ytproject/out/web
python3 tools/build.py
```

This copies `model.glb` and `guide3d.json` to `assets/3d/<slug>/`. The viewer (`src/viewer3d/main.js`) is bundled
with three.js 0.170 into `assets/3d/viewer.js`, served from this site like everything else. After changing it, run
`tools/build_viewer.sh` (needs Node) and then `python3 tools/build.py`. The 3D page loads about 150 KB of script and
160 KB of model (compressed), only on that page.

## Privacy

No cookies, analytics or third-party requests on page load. The YouTube player loads only after the visitor
presses play, from youtube-nocookie.com (the privacy policy says so).
