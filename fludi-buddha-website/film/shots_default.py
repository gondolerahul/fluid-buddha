"""Shots for the default world's scroll film (docs/marketing-docs/WebsitePlan.md §6).

Run from fludi-buddha-website/:
  .venv/Scripts/python film/pipeline.py keyframes --world default
  .venv/Scripts/python film/pipeline.py clips --world default --res 360p     # drafts
  .venv/Scripts/python film/pipeline.py stitch --world default --res 360p --fps 12

Nine keyframes (K0..K8) join eight shots. Four keyframes are the approved style frames
(K0 = D1, K2 = D3, K3 = D4, K6 = D7), copied in by `pipeline.py seed --world default`.

  shot  keyframes  seconds  chapter of the page
  S1    K0 -> K1   6        hero, then "A visitor has a question"
  S2    K1 -> K2   8        "It answers out loud, from your own pages"
  S3    K2 -> K3   8        "It draws charts, tables and calculators"
  S4    K3 -> K4   8        "It opens the right page" (a ring closes around one slab)
  S5    K4 -> K5   6        "It books the meeting after the visitor says yes"
  S6    K5 -> K6   8        "The page changes to fit each visitor"
  S7    K6 -> K7   6        "Tell us what you do" (the selector)
  S8    K7 -> K8   8        "One visitor in ten never sees it"
"""

IMAGE_MODEL = "gemini-3-pro-image"
# Tried in order; the first that works is used and recorded in the manifest.
VIDEO_MODELS = ["gemini-omni-1.2-flash", "gemini-omni-1.1-flash", "gemini-omni-flash-preview"]

# Style frames that already are keyframes: keyframe id -> file in film/out/styleframes/default/
SEED = {"K0": "D1", "K2": "D3", "K3": "D4", "K6": "D7"}

STYLE = """
Visual style (keep identical in every frame): a breathtaking, richly detailed cinematic 3D
render, like a title sequence for a prestige science-fiction film, for a calm premium brand.
A vast warm-black hall (colour #0a0908) whose floor is a sheet of still black water that mirrors
everything above it. The hero objects are thick slabs of smoked amber glass with bevelled,
polished edges that float upright above the water. Inside each slab, fine details are etched in
gold light: thin rules, small bars, dots, rings and grids, like the abstract skeleton of a web
page, never real writing. Thousands of tiny glowing gold dots drift through the air like fireflies
and gather into flowing ribbons. Volumetric shafts of warm light cut through a light haze; gold
caustics ripple on the water; reflections, refraction and soft bloom everywhere. Anamorphic
35mm lens, deep layered depth, rich contrast, a palette of only warm black, amber and gold
(#edab48) to pale champagne (#ffefd8). The composition fills the whole frame from edge to edge,
while the left third stays darker and calmer than the rest.
Strictly no text, no letters, no numbers, no logos, no people, no hands.
""".strip()

LAYOUTS = {}

KEYFRAMES = {
    "K1": {"refs": ["K0"], "prompt": """
Keep the hall, water, camera and the arrangement of the seven glass slabs exactly as in the
reference image. The thin ribbon of gold dots has now crossed the water and gathered into one
small, bright cluster that hovers right in front of the middle slab of the lower row of three.
That slab's etched lines have begun to glow where the cluster lights them, and a soft pool of
gold light shimmers on the water beneath it. All the other slabs are still dim, but each has
turned a few degrees to face the cluster, as if listening."""},
    "K4": {"refs": ["K3", "K0"], "prompt": """
Same hall, water, material and lighting as the reference images. The camera has glided to the
right, past the first group, and now looks at a second group of five glass slabs deeper in the
hall, arranged like another page: one wide slab on top and four below it. One of the lower slabs
is circled by a thin, bright halo of gold light that hovers around its edge like a ring, and
its etched details shine. A ribbon of gold dots streams in from the left of the frame and ends
at that ringed slab. The first group of slabs is visible at the left edge, soft and out of
focus. The left third of the frame stays darker."""},
    "K5": {"refs": ["K4"], "prompt": """
Keep the hall, water, camera and the second group of slabs as in the reference image. From the
ringed slab, a small glass card has slid forward towards the camera and hangs in the foreground,
glowing warmly, with one bright closed ring of gold light at its centre like a seal. A second
small glass card is flying away towards the far right of the frame, leaving a long, soft trail
of gold dots behind it, heading for a distant warm light. The halo around the lower slab has
faded to a gentle glow. The left third of the frame stays darker."""},
    "K7": {"refs": ["K6"], "prompt": """
Keep the hall, water, material and the warm sunrise glow from the reference image. The glass
slabs have gathered into three separate, neat stacks that stand side by side across the centre
and right of the frame, evenly spaced. Each stack is two or three slabs deep, slightly fanned
like cards, and each has its own small cluster of gold dots hovering just above it. Their
reflections stand in the water below. The left third of the frame stays the darkest part."""},
    "K8": {"refs": ["K7"], "prompt": """
Keep the hall, water and sunrise glow from the reference image; the three stacks of slabs have
drifted back and are now soft and out of focus in the distance. In the foreground, a row of ten
small glowing orbs floats in a line just above the water across the centre and right of the
frame: nine are bright gold and one is dim, grey and unlit. Above the orbs, two fine lines of
gold light run from left to right, starting together and slowly separating, the upper one
rising higher, like two lines of a chart. Bright, calm morning light. The left third of the
frame stays darker."""},
}

STILL = "Camera: locked off, perfectly still."
SHOTS = {
    "S1": {"from": "K0", "to": "K1", "seconds": 6, "camera": STILL,
           "prompt": "Every glass slab stays exactly where it is for the whole shot: same position, same size, same "
                     "spacing as in the first image. Nothing slides, drifts apart or regroups. The thin ribbon of gold "
                     "dots drifts slowly across the black water from the left towards the slabs, lighting the ripples "
                     "beneath it, and gathers into one small bright cluster in front of the middle slab of the lower "
                     "row. Only as it arrives does each slab turn a few degrees on the spot to face it. Slow, calm, "
                     "weightless."},
    "S2": {"from": "K1", "to": "K2", "seconds": 8, "camera": STILL,
           "prompt": "The cluster of dots streams into the large slab, which swings forward towards the camera and "
                     "comes alive: a wave of golden light begins to pulse across it like a voice. A horizontal ribbon "
                     "of gold dots grows in smoothly from the left edge of the frame, at the height of the large slab, "
                     "and flows into it. Three fine beams of gold light arc out from the slab to three smaller slabs, "
                     "whose etched details light up one after another. Caustics bloom on the water and shafts of light "
                     "fan out behind the slabs. The dots only ever form soft horizontal ribbons and loose swirls: no "
                     "vertical columns, walls, grids or curtains of dots anywhere, and nothing at the left edge except "
                     "the one horizontal ribbon."},
    "S3": {"from": "K2", "to": "K3", "seconds": 8,
           "camera": "Camera: a slow, steady push in towards the large slab.",
           "prompt": "The wave of light on the large slab settles, and the slab unfolds like origami: golden glass "
                     "columns of different heights rise smoothly out of its surface, a curved line of light sweeps "
                     "above them, thin glass strips stack up beside them like rows, and a small glowing sphere slides "
                     "along a rail of light. Smooth and continuous."},
    "S4": {"from": "K3", "to": "K4", "seconds": 8,
           "camera": "Camera: a slow, steady pull back to the wider view of the whole group of slabs.",
           "prompt": "The golden columns fold smoothly back into the large slab, which goes dim again. A ribbon of "
                     "gold dots lifts away from it and travels down to the slab at the right of the lower row. As the "
                     "ribbon arrives, a thin halo of gold light draws itself around that slab and closes into a "
                     "bright ring, and its etched details shine."},
    "S5": {"from": "K4", "to": "K5", "seconds": 6, "camera": STILL,
           "prompt": "From the ringed slab, a small glass card slides forward towards the camera, and a ring of gold "
                     "light closes at its centre like a seal. Then a second small glass card lifts away and flies "
                     "towards the far right, leaving a long trail of gold dots. The halo around the slab fades to a "
                     "gentle glow."},
    "S6": {"from": "K5", "to": "K6", "seconds": 8, "camera": STILL,
           "prompt": "The two small cards and the ring dissolve into gold dots. The slabs lift, glide past one "
                     "another and rearrange themselves into a new layout: a tall column on one side and a grid beside "
                     "it, leaving soft trails of gold dots. Ribbons of dots enter from different directions. Behind "
                     "everything, a warm glow rises like sunrise over the water."},
    "S7": {"from": "K6", "to": "K7", "seconds": 6, "camera": STILL,
           "prompt": "The slabs separate and drift calmly into three neat stacks standing side by side, each two or "
                     "three slabs deep and slightly fanned like cards. The three ribbons of gold dots settle into a "
                     "small cluster above each stack. Unhurried and precise."},
    "S8": {"from": "K7", "to": "K8", "seconds": 8,
           "camera": "Camera: a very slow drift forward and slightly down, towards the water.",
           "prompt": "The three stacks drift back into the distance and soften out of focus. The clusters of gold "
                     "dots flow forward and condense into a row of ten small orbs floating above the water; nine "
                     "brighten to gold and one stays dim and grey. Above them, two fine lines of gold light draw "
                     "themselves from left to right, starting together and slowly separating, the upper one rising."},
}
