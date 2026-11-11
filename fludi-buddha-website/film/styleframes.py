"""Style frames for the rendered films (phase 2 of docs/marketing-docs/WebsitePlan.md).

Three stills per world, to approve the look before any video is made:
  default    D1 D3 D4 D7   amber glass slabs over black water, streams of gold dots
  education  E1 E2 E6 E7   warm interiors with people (the only film with people)

Run from fludi-buddha-website/:
  .venv/Scripts/python film/styleframes.py              # all missing frames
  .venv/Scripts/python film/styleframes.py D3 --force   # remake one

Full-size PNGs go to film/out/styleframes/<world>/ (git-ignored). A 1600px JPEG of each is
copied to look/frames/ for the look pages. Every request is logged in film/out/manifest.json.
The API key is read from fludi-buddha-website/.env (GEMINI_API_KEY) and never written anywhere.
"""
import argparse
import io
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from PIL import Image

SITE = Path(__file__).resolve().parent.parent
OUT = SITE / "film" / "out"
LOOK = SITE / "look" / "frames"
load_dotenv(SITE / ".env")

IMAGE_MODEL = "gemini-3-pro-image"

STYLE = {
    "default": """
Visual style (keep identical in every frame): a breathtaking, richly detailed cinematic 3D
render, like a title sequence for a prestige science-fiction film, for a calm premium brand.
A vast warm-black hall (colour #0a0908) whose floor is a sheet of still black water that mirrors
everything above it. The hero objects are seven thick slabs of smoked amber glass with bevelled,
polished edges that float upright above the water. Inside each slab, fine details are etched in
gold light: thin rules, small bars, dots, rings and grids, like the abstract skeleton of a web
page, never real writing. Thousands of tiny glowing gold dots drift through the air like fireflies
and gather into flowing ribbons. Volumetric shafts of warm light cut through a light haze; gold
caustics ripple on the water; reflections, refraction and soft bloom everywhere. Anamorphic
35mm lens, deep layered depth with a softly blurred foreground element, rich contrast, a palette
of only warm black, amber and gold (#edab48) to pale champagne (#ffefd8). The composition fills
the whole frame from edge to edge, while the left third stays darker and calmer than the rest.
Strictly no text, no letters, no numbers, no logos, no people, no hands.
""",
    "education": """
Visual style (keep identical in every frame): photoreal cinematic still from a warm, quiet
family drama set in a middle-class Indian home and a university office. Natural, candid and
unposed. Soft warm practical light, cream walls, warm wood, muted fabrics, gentle golden
highlights, no blue or cold tones. 35mm lens, shallow depth of field, fine natural skin texture.
People are seen from behind, in profile or at mid-distance, and never look at the camera.
Any phone or laptop screen shows only soft glowing abstract rectangles of warm light.
Strictly no readable text, no letters, no numbers, no logos, no watermarks.
""",
}

FRAMES = {
    # ------------------------------------------------------------ default world
    "D1": {"world": "default", "prompt": """
Wide establishing shot. The seven glass slabs hang above the black water in the centre and
right of the frame, arranged like a web page seen at a slight angle: one long thin slab on top,
a large slab with a narrower one beside it, a row of three smaller slabs below, and one small
pill-shaped slab. They are almost dark: only their bevelled edges and a few etched lines glow
faintly. Far away on the left a single thin ribbon of gold dots is drifting in across the water
towards them, lighting the ripples beneath it. The hall is quiet, immense and waiting."""},
    "D3": {"world": "default", "refs": ["D1"], "prompt": """
Keep the hall, water, camera and slab arrangement from the reference image. The ribbon of gold
dots has arrived: it streams from the left of the frame straight into the large slab, which has
swung forward towards the camera and is now brilliantly alive, with a flowing wave of golden
light pulsing across it like a voice. From that slab, three fine beams of gold light arc back to
three of the smaller slabs, whose etched details light up in answer. Bright caustics dance on
the water below, light shafts fan out behind the slabs, and thousands of dots swirl around the
group. The left third of the frame stays darker, crossed only by the incoming ribbon."""},
    "D4": {"world": "default", "refs": ["D1"], "prompt": """
Keep the hall, water and lighting from the reference image, with the camera closer. The large
slab has unfolded like origami: golden bars of different heights rise out of its surface as
glowing glass columns, a curved line of light sweeps above them like a chart, and beside them
a row of thin glass strips stacks up like the rows of a table. One small glowing sphere rides a
horizontal rail of light like a slider. The other slabs float behind, softly out of focus.
Gold dots orbit the columns; their reflections stretch across the water. The left third of the
frame stays darker and calmer."""},
    "D7": {"world": "default", "refs": ["D1"], "prompt": """
Keep the hall, water, material and lighting from the reference image. The seven slabs are caught
in mid-flight, rearranging themselves into a new page layout: some have already settled into a
tall column on one side and a two-by-two grid beside it, while two are still gliding into place
and leave soft trails of gold dots behind them. Three separate ribbons of gold dots enter from
different directions and each lights a different part of the group. Behind everything a warm
glow rises like sunrise over the water, the brightest frame of the film. The left third of the
frame stays the darkest part."""},
    # ---------------------------------------------------------- education world
    "E1": {"world": "education", "prompt": """
Night in a small, tidy bedroom. A student of about nineteen, with short dark hair and a plain
cotton kurta, sits at a wooden study desk, seen from behind and slightly to the right, in the
right half of the frame. A brass desk lamp makes a warm pool of light over open notebooks. The
student holds a smartphone in one hand; its screen glows softly and lights the edge of their
face and hand. The left half of the frame is a dim cream wall and a dark window, calm and empty."""},
    "E2": {"world": "education", "refs": ["E1"], "prompt": """
The same student, room, desk and lamp as in the reference image, a moment later. Close
over-the-shoulder shot from behind and to the right: the student has raised the smartphone
towards their mouth and is speaking to it, seen in soft profile, relaxed and curious. The phone
screen glows with soft warm rectangles and lights their cheek and fingers. The notebooks and the
brass lamp are softly out of focus in the lower right. The left half of the frame is the dark
window and dim wall, calm and empty."""},
    "E6": {"world": "education", "refs": ["E1"], "prompt": """
The same student as in the reference image, same hair and kurta, now in the family living room
later that evening. The student is clearly a young adult of nineteen: adult height, lean adult
face and jaw, taller than the seated parent, not a child or young teenager. A parent, a woman of about fifty in a simple cotton salwar kameez with her
hair tied back, sits on a sofa in profile, reading something on her own smartphone with calm
attention and a slight smile. The student stands beside the sofa, leaning in a little, seen
from the side. A floor lamp gives warm light. They are in the right two-thirds of the frame;
the left third is a soft, out-of-focus cream wall with a wooden shelf."""},
    "E7": {"world": "education", "prompt": """
Morning in a bright university admissions office. A counsellor, a woman of about thirty with a
long braid, wearing a neat kurta, sits at a wooden desk at mid-distance in the right half of
the frame, seen in three-quarter profile. She holds a steel cup of tea in one hand and looks at
an open laptop that we see only from behind: the camera sees the plain back of its lid, never
the screen, and the lid has no logo. Warm morning sunlight comes through a
window with thin curtains and falls across the desk, files and a small potted plant. The left
half of the frame is a softly lit cream wall, calm and empty."""},
}


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


def make(c, fid, force=False):
    from google.genai import types
    spec = FRAMES[fid]
    d = OUT / "styleframes" / spec["world"]
    d.mkdir(parents=True, exist_ok=True)
    dest = d / f"{fid}.png"
    if dest.exists() and not force:
        print("skip (exists)", dest.name, flush=True)
    else:
        contents = []
        for ref in spec.get("refs", []):
            p = d / f"{ref}.png"
            if not p.exists():
                make(c, ref)
            contents.append(types.Part.from_bytes(data=p.read_bytes(), mime_type="image/png"))
        prompt = spec["prompt"].strip() + "\n\n" + STYLE[spec["world"]].strip()
        contents.append(prompt)
        t0 = time.time()
        resp = c.models.generate_content(
            model=IMAGE_MODEL, contents=contents,
            config=types.GenerateContentConfig(
                response_modalities=["IMAGE"],
                image_config=types.ImageConfig(aspect_ratio="16:9", image_size="2K")))
        data = None
        for part in resp.candidates[0].content.parts:
            if getattr(part, "inline_data", None) and part.inline_data.data:
                data = part.inline_data.data
        if not data:
            print(f"{fid}: no image returned ({resp.candidates[0].finish_reason})", flush=True)
            return None
        Image.open(io.BytesIO(data)).convert("RGB").save(dest)
        log({"kind": "styleframe", "id": fid, "world": spec["world"], "model": IMAGE_MODEL,
             "refs": spec.get("refs", []), "prompt": prompt,
             "file": str(dest.relative_to(SITE)), "seconds": round(time.time() - t0, 1)})
        print("styleframe", fid, f"{time.time() - t0:.0f}s", flush=True)
    LOOK.mkdir(parents=True, exist_ok=True)
    im = Image.open(dest).convert("RGB")
    im.thumbnail((1600, 1600))
    im.save(LOOK / f"{fid}.jpg", quality=84)
    return dest


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("ids", nargs="*")
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args()
    c = client()
    for fid in (a.ids or list(FRAMES)):
        try:
            make(c, fid, a.force)
        except Exception as e:  # keep going so one failed frame does not block the rest
            print(f"{fid}: FAILED {type(e).__name__}: {e}", flush=True)


if __name__ == "__main__":
    main()
