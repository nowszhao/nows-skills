"""
Helper script: extract dominant colors from an image.

Usage:
    python scripts/color_extractor.py <image_path> [--count N]

Example:
    python scripts/color_extractor.py screenshot.png --count 5

Requires: pip install Pillow scipy
"""

import argparse
import colorsys
import sys
from collections import Counter
from pathlib import Path
from typing import Sequence

try:
    from PIL import Image
except ImportError:
    print("Error: Pillow is required. Install with: pip install Pillow")
    sys.exit(1)

try:
    import numpy as np
    from scipy.cluster.vq import kmeans  # type: ignore[import-untyped]
except ImportError:
    print("Error: scipy + numpy are required. Install with: pip install scipy numpy")
    sys.exit(1)


def _rgb_to_hex(r: int, g: int, b: int) -> str:
    return f"#{r:02x}{g:02x}{b:02x}"


def _is_near_gray(r: int, g: int, b: int, threshold: int = 30) -> bool:
    return abs(r - g) < threshold and abs(g - b) < threshold and abs(r - b) < threshold


def extract_dominant_colors(
    image_path: str,
    n_colors: int = 8,
    downsample_size: int = 200,
    dedupe_threshold: int = 30,
) -> list[tuple[str, int, int, int, float]]:
    """
    Extract dominant colors from an image using k-means clustering.

    Returns a list of tuples: (hex_color, r, g, b, percentage)
    Sorted by percentage descending.
    """
    img = Image.open(image_path).convert("RGB")
    img.thumbnail((downsample_size, downsample_size), Image.LANCZOS)

    pixels = list(img.getdata())
    total = len(pixels)

    # Count color frequency (quantized to reduce noise)
    quantize = 16
    quantized = [(r // quantize * quantize, g // quantize * quantize, b // quantize * quantize) for r, g, b in pixels]
    color_counts = Counter(quantized)

    # Get top colors by frequency
    top_pixels = list(color_counts.keys())
    if len(top_pixels) > n_colors * 3:
        # Use k-means for better clustering
        codes, _ = kmeans(
            np.array([[r, g, b] for r, g, b in top_pixels], dtype=float),
            n_colors * 2,
            seed=42,
        )
        top_colors = [(int(c[0]), int(c[1]), int(c[2])) for c in codes]
    else:
        top_colors = top_pixels

    # Deduplicate near-duplicate colors
    unique: list[tuple[int, int, int]] = []
    for color in top_colors:
        if not any(
            abs(color[0] - u[0]) < dedupe_threshold
            and abs(color[1] - u[1]) < dedupe_threshold
            and abs(color[2] - u[2]) < dedupe_threshold
            for u in unique
        ):
            unique.append(color)

    # Calculate percentages related to top colors
    results: list[tuple[str, int, int, int, float]] = []
    for r, g, b in unique[:n_colors]:
        bucket = (r // 16 * 16, g // 16 * 16, b // 16 * 16)
        count = sum(
            v for k, v in color_counts.items() if tuple(k) == bucket
        )
        pct = (count / total) * 100
        results.append((_rgb_to_hex(r, g, b), r, g, b, pct))

    results.sort(key=lambda x: x[4], reverse=True)
    return results


def _color_role(r: int, g: int, b: int, index: int, total: int, lightest: tuple) -> str | None:
    """Guess the role of a color in a UI."""
    brightness = r * 0.299 + g * 0.587 + b * 0.114
    if index == 0:
        if brightness > 200:
            return "🖼 Background (light)"
        elif brightness < 50:
            return "🖼 Background (dark)"
        return "🖼 Background"
    if index == 1:
        if brightness > 128:
            return "📝 Primary text / surface"
        return "🎨 Brand accent / primary"
    if brightness < 50:
        return "📝 Dark text / heading"
    return None


def extract_colors_formatted(image_path: str, n_colors: int = 8) -> str:
    """Extract colors and return a formatted string for prompt use."""
    try:
        colors = extract_dominant_colors(image_path, n_colors=n_colors)
    except Exception as e:
        return f"[Error extracting colors: {e}]"

    lines = ["## Extracted Color Palette", "", "| Hex | RGB | % | Suggested Role |", "|-----|-----|---|----------------|"]

    lightest = max(colors, key=lambda c: c[1] + c[2] + c[3])[1:4]

    for i, (hex_c, r, g, b, pct) in enumerate(colors):
        role = _color_role(r, g, b, i, len(colors), lightest) or ""
        lines.append(f"| `{hex_c}` | ({r}, {g}, {b}) | {pct:.1f}% | {role} |")

    bg_color = colors[0] if colors else ("#fff", 255, 255, 255, 100)
    lines.append("")
    lines.append(f"```css\n/* Suggested CSS variables */")
    lines.append(f":root {{")
    for i, (hex_c, r, g, b, _) in enumerate(colors):
        if i == 0:
            lines.append(f"  --bg-primary: {hex_c};")
        elif i == 1:
            lines.append(f"  --text-primary: {hex_c};")
        elif i == 2:
            lines.append(f"  --accent: {hex_c};")
        else:
            lines.append(f"  --color-{i}: {hex_c};")
    lines.append("}")
    lines.append("```")

    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Extract dominant colors from an image for design-to-code use."
    )
    parser.add_argument("image", help="Path to the image file")
    parser.add_argument("--count", type=int, default=8, help="Number of colors to extract (default: 8)")
    args = parser.parse_args(argv)

    if not Path(args.image).exists():
        print(f"Error: File not found: {args.image}")
        sys.exit(1)

    print(extract_colors_formatted(args.image, n_colors=args.count))


if __name__ == "__main__":
    main()
