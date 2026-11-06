"""FluidBuddha film pipeline: layout masks -> keyframes (Gemini image) -> clips (Gemini Omni).

Usage (from fludi-buddha-website/):
  .venv/Scripts/python film/pipeline.py masks
  .venv/Scripts/python film/pipeline.py keyframes K0 K1 K2 ...   (omit ids = all)
  .venv/Scripts/python film/pipeline.py clips S01 S02 ...        (omit ids = all)
  .venv/Scripts/python film/pipeline.py stitch                   (joins clips, extracts frames)
Options:  --res 360p|720p|1080p|4k   --force   --aspect 16:9|9:16

The API key is read from fludi-buddha-website/.env (GEMINI_API_KEY) and never written anywhere.
Every request and output is logged to film/out/manifest.json so any shot can be re-made.
"""
import argparse
import base64
import io
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent
SITE = ROOT.parent
OUT = ROOT / "out"
load_dotenv(SITE / ".env")

sys.path.insert(0, str(ROOT))
from shots import IMAGE_MODEL, KEYFRAMES, LAYOUTS, SHOTS, STYLE, VIDEO_MODELS  # noqa: E402


def client():
    from google import genai
    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        sys.exit("GEMINI_API_KEY missing from fludi-buddha-website/.env")
    return genai.Client(api_key=key)


def log(entry):
    OUT.mkdir(parents=True, exist_ok=True)
    mf = OUT / "manifest.json"
    data = json.loads(mf.read_text(encoding="utf-8")) if mf.exists() else []
    entry["at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    data.append(entry)
    mf.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def size_for(aspect):
    return (1920, 1080) if aspect == "16:9" else (1080, 1920)


# ------------------------------------------------------------------ 1. masks
def make_masks(aspect):
    """Draw each layout as a plain mask: the shapes the liquid must settle into."""
    W, H = size_for(aspect)
    d = OUT / aspect.replace(":", "x") / "masks"
    d.mkdir(parents=True, exist_ok=True)
    for name, shapes in LAYOUTS.items():
        if aspect not in shapes:
            print("no", aspect, "layout for", name, "(skipped)")
            continue
        img = Image.new("RGB", (W, H), (246, 242, 234))
        dr = ImageDraw.Draw(img)
        for (x0, y0, x1, y1, r) in shapes[aspect]:
            box = [x0 * W, y0 * H, x1 * W, y1 * H]
            dr.rounded_rectangle(box, radius=r * H, fill=(150, 140, 125))
        img.save(d / f"{name}.png")
        print("mask", aspect, name)


# ------------------------------------------------------------------ 2. keyframes
def to_part(img_path):
    from google.genai import types
    return types.Part.from_bytes(data=Path(img_path).read_bytes(), mime_type="image/png")


def make_keyframe(c, kid, aspect, force=False):
    from google.genai import types
    spec = KEYFRAMES[kid]
    d = OUT / aspect.replace(":", "x") / "keyframes"
    d.mkdir(parents=True, exist_ok=True)
    dest = d / f"{kid}.png"
    if dest.exists() and not force:
        print("skip (exists)", dest.name)
        return dest
    contents, refs = [], []
    for ref in spec.get("refs", []):  # earlier keyframes (for continuity) and layout masks
        p = (d / f"{ref}.png") if ref.startswith("K") else (OUT / aspect.replace(":", "x") / "masks" / f"{ref}.png")
        if not p.exists():
            sys.exit(f"{kid} needs {p} first")
        contents.append(to_part(p))
        refs.append(p.name)
    prompt = spec["prompt"].strip() + "\n\n" + STYLE.strip()
    if aspect == "9:16":
        prompt += "\nVertical 9:16 composition: the same scene re-framed for a phone screen."
    contents.append(prompt)
    t0 = time.time()
    resp = c.models.generate_content(
        model=IMAGE_MODEL, contents=contents,
        config=types.GenerateContentConfig(
            response_modalities=["IMAGE"],
            image_config=types.ImageConfig(aspect_ratio=aspect, image_size="2K")))
    data = None
    for part in resp.candidates[0].content.parts:
        if getattr(part, "inline_data", None) and part.inline_data.data:
            data = part.inline_data.data
    if not data:
        sys.exit(f"{kid}: no image returned ({resp.candidates[0].finish_reason})")
    Image.open(io.BytesIO(data)).convert("RGB").save(dest)
    log({"kind": "keyframe", "id": kid, "aspect": aspect, "model": IMAGE_MODEL, "refs": refs,
         "prompt": prompt, "file": str(dest.relative_to(SITE)), "seconds": round(time.time() - t0, 1)})
    print("keyframe", kid, aspect, f"{time.time() - t0:.0f}s")
    return dest


# ------------------------------------------------------------------ 3. clips
def b64png(p, max_side=1280):
    im = Image.open(p).convert("RGB")
    im.thumbnail((max_side, max_side))
    buf = io.BytesIO()
    im.save(buf, format="JPEG", quality=92)
    return base64.b64encode(buf.getvalue()).decode()


def extract_video_bytes(interaction):
    ov = getattr(interaction, "output_video", None)
    if ov is not None and getattr(ov, "data", None):
        return ov.data if isinstance(ov.data, bytes) else base64.b64decode(ov.data)
    # REST-shaped fallback: steps -> model_output -> video
    raw = interaction.model_dump() if hasattr(interaction, "model_dump") else dict(interaction)
    for step in raw.get("steps", []) or []:
        for item in (step.get("model_output") or step.get("content") or []):
            if isinstance(item, dict) and item.get("type") == "video" and item.get("data"):
                return base64.b64decode(item["data"])
    raise RuntimeError("no video in response: keys=" + ",".join(raw.keys()))


def make_clip(c, sid, aspect, res, force=False):
    spec = SHOTS[sid]
    sub = aspect.replace(":", "x")
    kd = OUT / sub / "keyframes"
    d = OUT / sub / f"clips-{res}"
    d.mkdir(parents=True, exist_ok=True)
    dest = d / f"{sid}.mp4"
    if dest.exists() and not force:
        print("skip (exists)", dest.name)
        return dest
    first, last = kd / f"{spec['from']}.png", kd / f"{spec['to']}.png"
    for p in (first, last):
        if not p.exists():
            sys.exit(f"{sid} needs keyframe {p.name} first")
    prompt = ("The video starts EXACTLY on the first image and ends EXACTLY on the second image: the final frame "
              "must be identical to the second image (same camera framing, same objects, same sizes and positions). "
              "Do not add, remove or rearrange any element in the final frame.\n\n"
              + spec["prompt"].strip() + "\n\n" + spec.get("camera", "Camera: locked off, perfectly still.")
              + "\nNo text, no letters, no logos, no people, no hands. Silent: no music, no voices, no sound effects.")
    inp = [{"type": "image", "data": b64png(first), "mime_type": "image/jpeg"},
           {"type": "image", "data": b64png(last), "mime_type": "image/jpeg"},
           {"type": "text", "text": prompt}]
    fmt = {"type": "video", "duration": f"{spec['seconds']}s", "resolution": res, "aspect_ratio": aspect}
    last_err = None
    for model in VIDEO_MODELS:
        t0 = time.time()
        try:
            it = c.interactions.create(model=model, input=inp, response_format=fmt)
            data = extract_video_bytes(it)
        except Exception as e:  # try the next model id
            last_err = e
            print(f"  {model} failed: {str(e)[:200]}")
            continue
        dest.write_bytes(data)
        log({"kind": "clip", "id": sid, "aspect": aspect, "model": model, "format": fmt,
             "from": first.name, "to": last.name, "prompt": prompt, "interaction_id": getattr(it, "id", None),
             "file": str(dest.relative_to(SITE)), "seconds": round(time.time() - t0, 1)})
        print("clip", sid, model, res, f"{time.time() - t0:.0f}s", f"{len(data) // 1024} KB")
        return dest
    sys.exit(f"{sid}: all video models failed: {last_err}")


# ------------------------------------------------------------------ 4. stitch
def stitch(aspect, res):
    import imageio_ffmpeg
    ff = imageio_ffmpeg.get_ffmpeg_exe()
    sub = aspect.replace(":", "x")
    d = OUT / sub / f"clips-{res}"
    clips = [d / f"{sid}.mp4" for sid in SHOTS if (d / f"{sid}.mp4").exists()]
    if not clips:
        sys.exit("no clips to stitch")
    lst = d / "concat.txt"
    lst.write_text("".join(f"file '{p.name}'\n" for p in clips), encoding="utf-8")
    film = d / "film.mp4"
    subprocess.run([ff, "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(lst),
                    "-an", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18", "-g", "6", str(film)], check=True)
    frames = d / "frames"
    frames.mkdir(exist_ok=True)
    for f in frames.glob("*.jpg"):
        f.unlink()
    subprocess.run([ff, "-y", "-loglevel", "error", "-i", str(film), "-vf", "fps=24",
                    "-q:v", "3", str(frames / "f%05d.jpg")], check=True)
    n = len(list(frames.glob("*.jpg")))
    # Seam check: how far does each clip's last frame drift from the next clip's first frame?
    seams = []
    for a_, b_ in zip(clips, clips[1:]):
        fa, fb = d / f"_{a_.stem}_last.png", d / f"_{b_.stem}_first.png"
        subprocess.run([ff, "-y", "-loglevel", "error", "-sseof", "-0.3", "-i", str(a_), "-update", "1", str(fa)], check=True)
        subprocess.run([ff, "-y", "-loglevel", "error", "-i", str(b_), "-frames:v", "1", str(fb)], check=True)
        ia = Image.open(fa).convert("L").resize((160, 90))
        ib = Image.open(fb).convert("L").resize((160, 90))
        diff = sum(abs(x - y) for x, y in zip(ia.getdata(), ib.getdata())) / (160 * 90)
        seams.append({"between": f"{a_.stem}->{b_.stem}", "mean_abs_diff": round(diff, 1),
                      "ok": diff < 4})
        fa.unlink(); fb.unlink()
    for s_ in seams:
        print(f"  seam {s_['between']}: {s_['mean_abs_diff']} {'ok' if s_['ok'] else 'JUMP: regenerate or crossfade'}")
    (d / "film.json").write_text(json.dumps({"clips": [p.name for p in clips], "fps": 24, "frames": n,
                                             "seams": seams}, indent=2), encoding="utf-8")
    print("stitched", film.relative_to(SITE), "frames:", n)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["masks", "keyframes", "clips", "stitch"])
    ap.add_argument("ids", nargs="*")
    ap.add_argument("--aspect", default="16:9")
    ap.add_argument("--res", default="360p")
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args()
    if a.cmd == "masks":
        make_masks(a.aspect)
    elif a.cmd == "keyframes":
        c = client()
        for kid in (a.ids or list(KEYFRAMES)):
            make_keyframe(c, kid, a.aspect, a.force)
    elif a.cmd == "clips":
        c = client()
        for sid in (a.ids or list(SHOTS)):
            make_clip(c, sid, a.aspect, a.res, a.force)
    else:
        stitch(a.aspect, a.res)


if __name__ == "__main__":
    main()
