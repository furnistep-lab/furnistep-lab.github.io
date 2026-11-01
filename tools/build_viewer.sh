#!/bin/sh
# Bundle the 3D guide viewer (src/viewer3d/main.js + three.js) into assets/3d/viewer.js. Needs Node + npm.
# The bundle is committed, so GitHub Pages and CI never need Node. Run python3 tools/build.py afterwards
# (the viewer page's script URL carries a hash of the bundle).
set -eu
cd "$(dirname "$0")/.."
TMP="${TMPDIR:-/tmp}/furnistep-viewer-build"
mkdir -p "$TMP"
[ -f "$TMP/package.json" ] || (cd "$TMP" && npm init -y >/dev/null)
(cd "$TMP" && npm install --no-audit --no-fund three@0.170.0 esbuild@0.24.0 >/dev/null)
"$TMP/node_modules/.bin/esbuild" src/viewer3d/main.js --bundle --minify --format=esm --target=es2020 \
  --legal-comments=eof --alias:three="$TMP/node_modules/three" --outfile=assets/3d/viewer.js
