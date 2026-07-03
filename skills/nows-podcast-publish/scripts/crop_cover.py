#!/usr/bin/env python3
"""
Face-aware cover cropping for podcast artwork.

Reads a YouTube thumbnail, uses multimodal vision to identify face position,
crops a square that keeps the face fully visible (rule of thirds: face in upper 1/3),
and resizes to 1400x1400 for 小宇宙 requirements (360-5000 px square).

Usage:
    python3 scripts/crop_cover.py /tmp/cover_temp.jpg 620 0 1080 420 output_cover.png

Arguments:
    input_path   - Path to original YouTube thumbnail
    fx1 fy1 fx2 fy2 - Face bounding box coordinates (left, top, right, bottom)
    output_path  - Where to save the 1400x1400 cropped cover
"""

import sys
from PIL import Image


def crop_cover(input_path, face_box, output_path):
    """Crop and resize to 1400x1400 square, center on face position."""
    img = Image.open(input_path)
    w, h = img.size
    s = min(w, h)  # square side

    fx1, fy1, fx2, fy2 = face_box
    face_cx = (fx1 + fx2) // 2
    face_cy = (fy1 + fy2) // 2

    # Position square: face center at upper 1/3 (rule of thirds)
    left = max(0, face_cx - s // 2)
    top = max(0, face_cy - int(s * 0.35))
    left = min(left, w - s)
    top = min(top, h - s)

    # Validate face is fully inside crop
    assert fx1 >= left, f"Face left edge ({fx1}) outside crop left ({left})"
    assert fx2 <= left + s, f"Face right edge ({fx2}) outside crop right ({left + s})"
    assert fy1 >= top, f"Face top edge ({fy1}) outside crop top ({top})"
    assert fy2 <= top + s, f"Face bottom edge ({fy2}) outside crop bottom ({top + s})"

    cropped = img.crop((left, top, left + s, top + s))
    cropped = cropped.resize((1400, 1400), Image.LANCZOS)
    cropped.save(output_path)

    print(f"Cropped ({left},{top})-({left+s},{top+s}) from {w}x{h}")
    print(f"Face center at ({face_cx - left}, {face_cy - top}) in {s}x{s} square")
    print(f"Saved: {output_path} (1400x1400)")


if __name__ == "__main__":
    if len(sys.argv) != 7:
        print("Usage: crop_cover.py <input> <fx1> <fy1> <fx2> <fy2> <output>")
        sys.exit(1)

    input_path = sys.argv[1]
    face_box = tuple(map(int, sys.argv[2:6]))
    output_path = sys.argv[6]

    crop_cover(input_path, face_box, output_path)
