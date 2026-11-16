#!/usr/bin/env bash
# Converts every photo in src-images/ to WebP in up to 4 widths (480, 720, 960, 1600 px), never wider than the original.
# The build reads the widths from the file names.
# Needs cwebp (brew install webp) and sips (macOS).
set -euo pipefail
cd "$(dirname "$0")"
mkdir -p static/img
for src in src-images/*.jpg src-images/*.png; do
  [ -e "$src" ] || continue
  name=$(basename "${src%.*}")
  width=$(sips -g pixelWidth "$src" | awk '/pixelWidth/{print $2}')
  # Widths below the original, plus the original itself when it is under 1600 px.
  widths=""
  for w in 480 720 960 1600; do [ "$w" -lt "$width" ] && widths="$widths $w"; done
  [ "$width" -lt 1600 ] && widths="$widths $width"
  for w in $widths; do
    out="static/img/$name-$w.webp"
    [ "$out" -nt "$src" ] && continue
    cwebp -quiet -q 72 -m 6 -resize "$w" 0 -metadata none "$src" -o "$out"
  done
done
# Social sharing image, 1200x630 JPEG (Facebook, WhatsApp).
if [ ! static/og.jpg -nt src-images/facade.jpg ]; then
  sips -s format jpeg -s formatOptions 78 --resampleWidth 1200 src-images/facade.jpg --out static/og.jpg >/dev/null
  sips --cropToHeightWidth 630 1200 static/og.jpg >/dev/null
fi
du -sh static/img
