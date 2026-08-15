# NEXARA Brand Assets — MANIFEST

Source: `/Users/agentos/NEXARA-PRIME/ui/src/app/icon.svg`
Design: 门 + 金点 (ADR-UI-001)
- 石墨 #322F2A 圆角方 (rounded rect, rx=13)
- 象牙 #FDFAF5 门框 (右上断口)
- 金点 #C4A45A (完成/批准时刻)

Generation tool: cairosvg 2.9.0 (CLI, /opt/homebrew/bin/cairosvg)
Method: direct vector render at target size (no bitmap downscaling), PNG format,
with anti-aliasing from the vector source.

| File | Dimensions | Bytes | Method |
|------|-----------|-------|--------|
| icon_16.png        | 16x16   | 432   | cairosvg direct render @16px |
| icon_32.png        | 32x32   | 582   | cairosvg direct render @32px |
| icon_64.png        | 64x64   | 1161  | cairosvg direct render @64px |
| icon_128.png       | 128x128 | 2289  | cairosvg direct render @128px |
| icon_256.png       | 256x256 | 4851  | cairosvg direct render @256px |
| icon_512.png       | 512x512 | 10721 | cairosvg direct render @512px |
| icon_1024.png      | 1024x1024 | 23509 | cairosvg direct render @1024px |
| icon_1024_mono.png | 1024x1024 | 11844 | cairosvg direct render @1024px (mono) |

## Monochrome variant
icon_1024_mono.png is a single-color graphite glyph: the door frame strokes and
gold dot are all recolored to graphite #322F2A on a transparent background
(rounded-square background removed). Source: icon_mono.svg (build artifact in
this directory).

## Verification (Pillow 12.3.0, real pixel reads)
icon_1024.png:
- background pixel (128,128)   = (50, 47, 42, 255)   → graphite #322F2A ✓
- door top stroke (432,320)    = (253, 250, 245, 255) → ivory #FDFAF5 ✓
- door left (320,544)          = (253, 250, 245, 255) → ivory ✓
- door right (704,560)         = (253, 250, 245, 255) → ivory ✓
- gold dot center (512,528)    = (196, 164, 90, 255)  → gold #C4A45A ✓
- rounded corner (32,32)       = (0, 0, 0, 0)         → transparent ✓

icon_1024_mono.png:
- door top stroke (432,320)    = (50, 47, 42, 255) → graphite #322F2A ✓
- dot center (512,528)         = (50, 47, 42, 255) → graphite ✓
- background (128,128)         = (0, 0, 0, 0)      → transparent ✓

All dimensions confirmed via `sips -g pixelWidth -g pixelHeight`.
