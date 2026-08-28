#!/usr/bin/env python3
"""Generate the 柏韩 (NEXARA-PRIME) macOS app icon — 1024×1024 PNG.

Design: Sovereign Core
- Deep warm charcoal background with radial gradient
- Luminous hexagonal crystal with champagne gold rim + warm ivory glow
- Two concentric orbital rings
- Subtle light particles representing distributed intelligence
"""

import math
import os
from PIL import Image, ImageDraw, ImageFilter

OUTPUT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_PATH = os.path.join(OUTPUT_DIR, "Resources", "AppIcons", "nexara_sovereign_core.png")
PREVIEW_PATH = os.path.join(OUTPUT_DIR, "Resources", "AppIcons", "previews", "nexara_sovereign_core_preview.png")
SIZE = 1024
CX, CY = SIZE / 2, SIZE / 2


def hex_to_rgb(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    return tuple(int(h[i : i + 2], 16) for i in (0, 2, 4))


# ── Palette ──
WARM_IVORY = hex_to_rgb("F5F0E8")
CHAMPAGNE_GOLD = hex_to_rgb("C49A55")
CHAMPAGNE_LIGHT = hex_to_rgb("D8B878")
GRAPHITE = hex_to_rgb("302F2D")
GRAPHITE_LIGHT = hex_to_rgb("4A4742")
GRAPHITE_DEEP = hex_to_rgb("1F1E1C")
DUST_ROSE = hex_to_rgb("D58F98")
MOSS_GREEN = hex_to_rgb("72865D")


def lerp(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def dist(x1, y1, x2, y2):
    return math.sqrt((x1 - x2) ** 2 + (y1 - y2) ** 2)


def draw_radial_gradient(draw, img_size, center_color, edge_color):
    """Draw pixel-level radial gradient from center to edges."""
    w, h = img_size, img_size
    max_dist = dist(0, 0, w / 2, h / 2)
    for y in range(0, h, 2):  # step by 2 for performance, bilinear-like
        for x in range(0, w, 2):
            d = dist(x, y, w / 2, h / 2)
            t = min(d / max_dist, 1.0)
            # ease-in-out for natural falloff
            t = t ** 1.6
            color = lerp(center_color, edge_color, t)
            draw.rectangle([x, y, x + 1, y + 1], fill=color)


def hex_corner(cx, cy, radius, i):
    """Return (x, y) for i-th corner of a flat-top hexagon (i = 0..5)."""
    angle_deg = 60 * i - 30  # flat-top: start at -30°
    angle_rad = math.radians(angle_deg)
    return cx + radius * math.cos(angle_rad), cy + radius * math.sin(angle_rad)


def draw_hex(draw, cx, cy, radius, fill_color, outline_color, outline_width):
    """Draw a filled hexagon with outline."""
    pts = [hex_corner(cx, cy, radius, i) for i in range(6)]
    if fill_color is not None:
        draw.polygon(pts, fill=fill_color, outline=outline_color, width=outline_width)
    else:
        draw.polygon(pts, outline=outline_color, width=outline_width)


def draw_ring(draw, cx, cy, radius, color, width):
    """Draw a thin circular ring."""
    if len(color) == 4:
        draw.ellipse(
            [cx - radius, cy - radius, cx + radius, cy + radius],
            outline=color,
            width=width,
        )
    else:
        draw.ellipse(
            [cx - radius, cy - radius, cx + radius, cy + radius],
            outline=color,
            width=width,
        )


def glow_hex(img, cx, cy, outer_radius, glow_color, steps=12):
    """Add soft glow layers around the hexagon."""
    for i in range(steps, 0, -1):
        r = outer_radius + i * 3
        alpha = int(25 * (1 - i / steps))
        color_with_alpha = glow_color[:3] + (alpha,)
        overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
        odraw = ImageDraw.Draw(overlay)
        pts = [hex_corner(cx, cy, r, j) for j in range(6)]
        odraw.polygon(pts, outline=color_with_alpha, width=max(1, i // 3))
        img = Image.alpha_composite(img, overlay)
    return img


def main():
    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    os.makedirs(os.path.dirname(PREVIEW_PATH), exist_ok=True)

    # ── Base canvas ──
    img = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # ── Background: radial gradient from GRAPHITE_LIGHT to GRAPHITE_DEEP ──
    draw_radial_gradient(draw, SIZE, GRAPHITE_LIGHT, GRAPHITE_DEEP)

    # ── Subtle background texture: very faint concentric rings ──
    for r in range(100, 500, 60):
        alpha = 3
        draw_ring(draw, CX, CY, r, GRAPHITE + (alpha,), 1)

    # ── Outer orbital ring (warm ivory, thin) ──
    draw_ring(draw, CX, CY, 310, WARM_IVORY + (28,), 2)
    draw_ring(draw, CX, CY, 312, WARM_IVORY + (10,), 1)

    # ── Inner orbital ring (champagne gold) ──
    draw_ring(draw, CX, CY, 240, CHAMPAGNE_GOLD + (50,), 3)
    draw_ring(draw, CX, CY, 238, CHAMPAGNE_LIGHT + (20,), 1)

    # ── Hexagonal crystal core ──
    hex_radius = 130

    # Draw hex glow layers on a separate image for compositing
    img = glow_hex(img, CX, CY, hex_radius, CHAMPAGNE_GOLD + (20,), steps=10)

    # Main hex body
    draw = ImageDraw.Draw(img)
    # Inner fill: warm ivory with slight gradient illusion
    inner_color = lerp(WARM_IVORY, CHAMPAGNE_LIGHT, 0.15)
    draw_hex(draw, CX, CY, hex_radius, inner_color, CHAMPAGNE_GOLD, 6)

    # Inner hex: slightly smaller, brighter core
    draw_hex(draw, CX, CY, hex_radius - 22, WARM_IVORY, CHAMPAGNE_LIGHT, 3)

    # Center dot: warm ivory bright center
    dot_r = 16
    draw.ellipse(
        [CX - dot_r, CY - dot_r, CX + dot_r, CY + dot_r],
        fill=WARM_IVORY,
        outline=CHAMPAGNE_GOLD,
        width=2,
    )

    # ── Light particles / nodes ──
    particle_positions = []
    # Ring particles along the orbital rings
    for ring_r, count, base_angle in [(310, 12, 15), (240, 8, 0)]:
        for i in range(count):
            angle = math.radians(base_angle + 360 * i / count)
            px = CX + ring_r * math.cos(angle)
            py = CY + ring_r * math.sin(angle)
            particle_positions.append((px, py, "ring"))

    # Scattered particles in the space between rings
    import random

    random.seed(42)
    for _ in range(18):
        angle = random.uniform(0, 2 * math.pi)
        r = random.uniform(150, 380)
        px = CX + r * math.cos(angle)
        py = CY + r * math.sin(angle)
        particle_positions.append((px, py, "scatter"))

    for px, py, ptype in particle_positions:
        if ptype == "ring":
            size = 4
            color = CHAMPAGNE_LIGHT + (180,)
        else:
            size = random.uniform(1.5, 3.5)
            alpha = random.randint(30, 100)
            if random.random() < 0.4:
                color = WARM_IVORY + (alpha,)
            elif random.random() < 0.5:
                color = CHAMPAGNE_GOLD + (alpha,)
            else:
                color = DUST_ROSE + (alpha,)

        draw.ellipse(
            [px - size, py - size, px + size, py + size],
            fill=color,
        )

    # ── Subtle highlight arc (top-left light catch) ──
    # Creates a glass/3D feel on the dark background
    highlight_overlay = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    hd = ImageDraw.Draw(highlight_overlay)
    for i in range(8):
        alpha = int(12 * (1 - i / 8))
        r = 380 + i * 8
        hd.ellipse(
            [CX - r, CY - r - 120, CX + r, CY + r - 120],
            outline=(255, 255, 255, alpha),
            width=1,
        )
    img = Image.alpha_composite(img, highlight_overlay)

    # ── Apply subtle noise/grain for premium texture ──
    img_rgba = img.convert("RGBA")
    pixels = img_rgba.load()
    random.seed(7)
    for y in range(0, SIZE, 4):
        for x in range(0, SIZE, 4):
            r, g, b, a = pixels[x, y]
            noise = random.randint(-3, 3)
            pixels[x, y] = (
                max(0, min(255, r + noise)),
                max(0, min(255, g + noise)),
                max(0, min(255, b + noise)),
                a,
            )

    # ── Save ──
    img_rgba.save(OUTPUT_PATH, "PNG")
    print(f"Icon saved: {OUTPUT_PATH}")

    # ── Preview (256×256) ──
    preview = img_rgba.resize((256, 256), Image.LANCZOS)
    preview.save(PREVIEW_PATH, "PNG")
    print(f"Preview saved: {PREVIEW_PATH}")

    print("Done. Icon generated at 1024×1024 px.")


if __name__ == "__main__":
    main()
