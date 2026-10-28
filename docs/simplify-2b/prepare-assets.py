"""One-off SIMPLIFY-2B export preparation; not an application image subsystem.

Usage: python prepare-assets.py APPROVED_ILLUSTRATIONS_DIR GENERATED_IMAGES_DIR
Requires Pillow and numpy. Never regenerates or redesigns the approved characters.
"""
from collections import deque
from pathlib import Path
import hashlib
import json
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parents[2]
ASSETS = ROOT / "fe/public/illustrations"
DOCS = Path(__file__).resolve().parent
CHARACTERS = ["gco-character-point-right", "gco-character-point-up",
              "gco-character-wave", "gco-characters"]
OBJECTS = {
    "appointment-calendar-3d": "exec-74ff3358-9a0b-4afe-a2e8-6e34545608c9.png",
    "service-catalog-3d": "exec-26c6e813-2cf5-4284-bbf1-ea4af2b44b52.png",
    "guidance-messages-3d": "exec-9818a79f-79d2-480c-8c6d-3759fdd48a58.png",
    "individual-inventory-3d": "exec-babe0ae9-45f3-4b1a-a971-29944c118854.png",
    "counseling-3d": "exec-ad237f7d-634b-4f48-b3e7-7460bcde4021.png",
    "guidance-followups-3d": "exec-9380e30e-c80e-4e8b-8d29-b7c654f0fc23.png",
    "good-moral-3d": "exec-be5ade87-2f91-4320-9738-56aa47965bd6.png",
    "exit-interview-3d": "exec-8654c8b3-a99c-4eaf-ad53-05f0a854bc5a.png",
    "graduate-tracer-3d": "exec-6f78a5ed-bfb1-408f-9dbe-865504550cd7.png",
    "announcements-3d": "exec-cda247fb-cef2-45b8-9eef-489f00f86b46.png",
}

def erode(mask, size):
    return np.asarray(Image.fromarray(mask.astype("uint8") * 255)
                      .filter(ImageFilter.MinFilter(size))) > 127

def components(mask, minimum=250):
    h, w = mask.shape
    pending = mask.copy()
    result = np.zeros_like(mask)
    sizes = []
    for y, x in zip(*np.where(mask)):
        if not pending[y, x]:
            continue
        pending[y, x] = False
        queue = deque([(int(y), int(x))])
        points = []
        while queue:
            yy, xx = queue.popleft()
            points.append((yy, xx))
            for ny, nx in ((yy-1, xx), (yy+1, xx), (yy, xx-1), (yy, xx+1)):
                if 0 <= ny < h and 0 <= nx < w and pending[ny, nx]:
                    pending[ny, nx] = False
                    queue.append((ny, nx))
        if len(points) > minimum:
            ys, xs = zip(*points)
            result[ys, xs] = True
            sizes.append(len(points))
    return result, sizes

def clean_object(source, name):
    pixels = np.asarray(source).copy()
    mask, _ = components(pixels[:, :, 3] > 150, minimum=3000)
    mask = erode(mask, 5)
    mask, sizes = components(mask, minimum=3000)
    assert len(sizes) == (3 if name == "counseling-3d" else 1), (name, sizes)
    core = erode(mask, 7)
    colors = pixels[:, :, :3].astype("float32")
    known = core.copy()
    h, w = core.shape
    # Propagate uncontaminated interior colors through the thin fringe band.
    for _ in range(7):
        total = np.zeros_like(colors)
        weight = np.zeros((h, w), dtype="float32")
        for dy, dx in ((-1, 0), (1, 0), (0, -1), (0, 1),
                       (-1, -1), (-1, 1), (1, -1), (1, 1)):
            dst = (slice(max(0, dy), min(h, h+dy)), slice(max(0, dx), min(w, w+dx)))
            src = (slice(max(0, -dy), min(h, h-dy)), slice(max(0, -dx), min(w, w-dx)))
            valid = known[src]
            weight[dst] += valid
            total[dst] += colors[src] * valid[:, :, None]
        frontier = (~known) & (weight > 0)
        colors[frontier] = total[frontier] / weight[frontier, None]
        known[frontier] = True
    alpha = Image.fromarray(mask.astype("uint8") * 255).filter(ImageFilter.GaussianBlur(0.55))
    result = Image.fromarray(np.clip(colors, 0, 255).astype("uint8")).convert("RGBA")
    result.putalpha(alpha)
    result = result.crop(result.getbbox())
    result.thumbnail((416, 416), Image.Resampling.LANCZOS)
    canvas = Image.new("RGBA", (512, 512))
    canvas.alpha_composite(result, ((512-result.width)//2, (512-result.height)//2))
    return canvas

def export(name, source_path, is_object):
    source = Image.open(source_path).convert("RGBA")
    assert source.getchannel("A").getextrema() == (0, 255)
    if is_object:
        result = clean_object(source, name)
    else:
        # Uniform resampling only; preserve approved composition, alpha and colors.
        target = (1024, 512) if name == "gco-characters" else (512, 512)
        result = source.resize(target, Image.Resampling.LANCZOS)
    pixels = np.asarray(result).copy()
    pixels[:, :, 3][pixels[:, :, 3] < 3] = 0
    pixels[:, :, :3][pixels[:, :, 3] == 0] = 0
    result = Image.fromarray(pixels)
    path = ASSETS / f"{name}.png"
    result.save(path, optimize=True, compress_level=9)
    bounds = result.getbbox()
    padding = [bounds[0], bounds[1], result.width-bounds[2], result.height-bounds[3]]
    _, sizes = components(np.asarray(result.getchannel("A")) > 127)
    assert len(sizes) == (4 if name == "gco-characters" else 3 if name == "counseling-3d" else 1)
    assert min(padding) >= 20
    assert path.stat().st_size < (600_000 if name == "gco-characters" else 300_000)
    return result, {
        "file": path.relative_to(ROOT).as_posix(),
        "source": source_path.name,
        "source_kind": "generated object" if is_object else "approved local 3D character",
        "source_sha256": hashlib.sha256(source_path.read_bytes()).hexdigest(),
        "source_dimensions": list(source.size),
        "dimensions": list(result.size),
        "bytes": path.stat().st_size,
        "alpha_extrema": list(result.getchannel("A").getextrema()),
        "padding_px": padding,
        "silhouettes": len(sizes),
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
    }

def sheet(images, dark=False):
    bg, fg = ("#222a2d", "#fffdf8") if dark else ("#f7f3ea", "#222a2d")
    canvas = Image.new("RGB", (1800, 1440), bg)
    draw = ImageDraw.Draw(canvas)
    try:
        font = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial.ttf", 22)
    except OSError:
        font = ImageFont.load_default(size=22)
    draw.text((35, 25), "COMPASS / SIMPLIFY-2B — approved characters and matching objects", fill=fg, font=font)
    def place(name, box, label):
        image = images[name].copy()
        image.thumbnail((box[2]-box[0], box[3]-box[1]), Image.Resampling.LANCZOS)
        canvas.paste(image, (box[0]+(box[2]-box[0]-image.width)//2,
                             box[1]+(box[3]-box[1]-image.height)//2), image)
        draw.text((box[0]+15, box[3]+10), label, fill=fg, font=font)
    place("gco-characters", (20, 90, 880, 465), "Approved group")
    for i, name in enumerate(CHARACTERS[:3]):
        place(name, (900+i*290, 90, 1180+i*290, 465), ["Point right", "Point up", "Wave"][i])
    for i, name in enumerate(OBJECTS):
        row, col = divmod(i, 5)
        place(name, (15+col*357, 555+row*405, 352+col*357, 895+row*405),
              ["Appointments", "Service Catalog", "Guidance Messages", "Individual Inventory", "Counseling",
               "Follow-Ups", "Good Moral", "Exit Interview", "Graduate Tracer", "Announcements"][i])
    path = ROOT / "outputs/simplify-2b/contact-sheet-dark.png" if dark else DOCS / "contact-sheet.png"
    path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(path, optimize=True)

if __name__ == "__main__":
    approved, generated = map(Path, sys.argv[1:3])
    images, manifest = {}, []
    for name in CHARACTERS:
        images[name], row = export(name, approved / f"{name}.png", False)
        manifest.append(row)
    for name, filename in OBJECTS.items():
        images[name], row = export(name, generated / filename, True)
        manifest.append(row)
    sheet(images)
    sheet(images, dark=True)
    (DOCS / "asset-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps(manifest, indent=2))
