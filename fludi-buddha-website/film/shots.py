"""Shot definitions for the FluidBuddha home film.

Style test = the first four shots of WebsiteConcept.md §8:
  S01 Drop · S02 Splash to website · S03 Dusk · S04 Freeze
Keyframes K0..K4 are the joins: each shot interpolates from one keyframe to the next,
so shot N always ends exactly where shot N+1 begins.
"""

IMAGE_MODEL = "gemini-3-pro-image"
# Tried in order; the first that works is used and recorded in the manifest.
VIDEO_MODELS = ["gemini-omni-1.2-flash", "gemini-omni-1.1-flash", "gemini-omni-flash-preview"]

STYLE = """
Visual style (keep identical in every frame): ultra-premium product photography for a luxury
brand. A seamless, warm off-white studio infinity curve (colour #f6f2ea) with no visible horizon line,
soft diffused overhead light and a gentle floor shadow gradient. The hero material is liquid glass: crystal clear,
polished, with a warm gold core and gold caustic highlights (gold #edab48 to pale champagne
#ffefd8), like fine jewellery photographed on white. 85mm lens, shallow depth of field, calm,
minimal, vast negative space. Photorealistic, high dynamic range, no grain, no vignette.
Strictly no text, no letters, no numbers, no logos, no icons, no people, no hands.
""".strip()

# Layout masks: (x0, y0, x1, y1, corner radius) as fractions of the frame.
# Layout 1 = the "website" the splash crystallises into (home film, chapter 1).
# In 16:9 it sits in the right ~55% so the left third stays empty for the HTML headline.
LAYOUTS = {
    "layout1": {
        "16:9": [
            (0.40, 0.17, 0.94, 0.215, 0.012),   # navigation bar
            (0.40, 0.25, 0.70, 0.52, 0.02),     # hero panel
            (0.72, 0.25, 0.94, 0.52, 0.02),     # side panel
            (0.40, 0.56, 0.57, 0.76, 0.02),     # card 1
            (0.585, 0.56, 0.755, 0.76, 0.02),   # card 2
            (0.77, 0.56, 0.94, 0.76, 0.02),     # card 3
            (0.40, 0.79, 0.50, 0.83, 0.02),     # pill button
        ],
        "9:16": [
            (0.08, 0.38, 0.92, 0.405, 0.008),
            (0.08, 0.425, 0.92, 0.58, 0.012),
            (0.08, 0.60, 0.49, 0.74, 0.012),
            (0.51, 0.60, 0.92, 0.74, 0.012),
            (0.08, 0.76, 0.92, 0.84, 0.012),
            (0.08, 0.86, 0.40, 0.885, 0.012),
        ],
    },
}

KEYFRAMES = {
    "K0": {
        "prompt": """
An empty, calm scene: a seamless warm off-white studio infinity curve, with NO visible
horizon line or edge where floor meets wall: the floor curves softly up into the background.
Lying on the floor in the centre-right of the frame is a shallow puddle of LIQUID (not a dish,
not a plate, not a solid object): clear liquid glass with a faint warm gold tint, soft organic
irregular edges held by surface tension, a gentle rounded meniscus at its rim, its surface
perfectly still and mirror-like, catching soft reflections. Nothing else. The left third of the
frame is empty space.""",
    },
    "K1": {
        "refs": ["K0"],
        "prompt": """
Keep the camera, lighting, background and pool exactly as in the reference image.
Add a single droplet of liquid gold-glass hanging in mid-air above the centre of the pool,
frozen in extreme slow motion, slightly elongated by its fall, crystal clear with a warm gold
core and bright caustic highlights. The droplet is small and precious. Nothing else changes.""",
    },
    "K2": {
        "refs": ["K1", "layout1"],
        "prompt": """
The first reference image is the scene; keep its camera, lighting, background and pool exactly.
The second reference image is a layout mask: grey rounded rectangles on a pale background.
The liquid from the pool has risen and crystallised into a floating, minimal website interface
made of polished clear liquid glass with warm gold edges and soft gold light inside it, placed
EXACTLY where the grey rectangles are in the mask: a thin navigation bar at the top, a large
panel and a smaller panel side by side, three equal cards in a row below, and a small pill
button. Every panel is completely blank and smooth: no text, no icons, no images, no lines.
The panels float slightly above the pool, which reflects them. Thin streams of liquid still
connect the bottom panels to the pool. The left third of the frame stays empty.""",
    },
    "K3": {
        "refs": ["K2"],
        "prompt": """
Keep the camera, composition and every glass panel exactly as in the reference image.
It is now night: the background is a warm near-black (#0a0908) instead of white, the light is
low and warm, and the glass interface glows softly from within with warm gold light. Far behind,
out of focus, a few warm city lights form soft bokeh. The pool reflects the glow.
Calm, quiet, luxurious.""",
    },
    "K4": {
        "refs": ["K3"],
        "prompt": """
Keep the camera, composition and every glass panel exactly as in the reference image.
Keep it night: the floor AND the background stay the same warm near-black (#0a0908) as in the
reference, with the same distant out-of-focus city lights; the floor must NOT become white or
bright. The glass interface has frozen: every panel is frosted over, matte, opaque,
covered in fine cold ice crystals, pale blue-grey. The warm gold glow inside has faded almost
completely. The pool below is still and dull. The mood is cold, silent and lifeless.""",
    },
}

SHOTS = {
    "S01": {"from": "K0", "to": "K1", "seconds": 6,
            "prompt": "A single droplet of liquid gold-glass falls into the frame from above in extreme slow motion, "
                      "slowing down until it hangs just above the centre of the still pool. Elegant, calm, weightless."},
    "S02": {"from": "K1", "to": "K2", "seconds": 8,
            "prompt": "The droplet touches the pool. A slow-motion crown splash rises, freezes for a moment, and its "
                      "liquid flows upward and crystallises into exactly seven floating glass panels: one thin bar on top, "
                      "two panels side by side, three cards in a row, and one small pill, arranged exactly as in the final "
                      "image and no larger. Viscous, smooth, continuous motion; the panels sharpen into crisp glass at the end."},
    "S03": {"from": "K2", "to": "K3", "seconds": 6,
            "prompt": "Time passes from day to night. The soft daylight slowly fades, the white background darkens to a "
                      "warm near-black, and the glass interface begins to glow softly from within with warm gold light. "
                      "Nothing else moves."},
    "S04": {"from": "K3", "to": "K4", "seconds": 8,
            "prompt": "Frost slowly spreads across every glass panel, creeping from the edges inward, until all panels "
                      "are matte, opaque and cold. The warm gold glow fades to a cold grey. Slow and silent."},
}


# =====================================================================================
# Shots S05-S14 (+ two seamless loops). Night runs from S03 to S10B; dawn returns in S11.
# The story is the SaaS buyer from WebsiteConcept.md section 7.1 (Meera, Northwind CRM).
# =====================================================================================
NIGHT = ("It is night: the floor and background are a warm near-black (#0a0908) with a few distant, "
         "out-of-focus warm city lights; the glass glows softly from within with warm gold light.")
KEEP = "Keep the camera position, lens, lighting and background exactly as in the first reference image."
BLANK = "Every panel is completely blank and smooth: no text, no icons, no images, no lines."
LEFT = "The left third of the frame stays empty."

LAYOUTS.update({
    # S06: the answer - a conversation column, a price card and a three-node flowchart
    "layout2": {"16:9": [
        (0.71, 0.17, 0.94, 0.83, 0.02),      # conversation column
        (0.40, 0.17, 0.67, 0.42, 0.02),      # price card
        (0.40, 0.50, 0.48, 0.63, 0.02),      # flowchart node 1
        (0.505, 0.50, 0.585, 0.63, 0.02),    # node 2
        (0.61, 0.50, 0.69, 0.63, 0.02),      # node 3
        (0.48, 0.558, 0.505, 0.572, 0.004),  # connector 1
        (0.585, 0.558, 0.61, 0.572, 0.004),  # connector 2
    ]},
    # S07: the page has scrolled; one section (security) is ringed
    "layout3": {"16:9": [
        (0.45, 0.10, 0.83, 0.20, 0.02),
        (0.45, 0.23, 0.83, 0.42, 0.02),
        (0.45, 0.45, 0.83, 0.64, 0.02),      # the ringed section
        (0.45, 0.67, 0.83, 0.88, 0.02),
    ]},
    # S08: the booking card
    "layout4": {"16:9": [
        (0.50, 0.28, 0.86, 0.62, 0.03),      # booking card
        (0.55, 0.52, 0.70, 0.575, 0.03),     # its pill button
    ]},
    # S12: a small website rising from the pool
    "layout6": {"16:9": [
        (0.52, 0.26, 0.88, 0.29, 0.008),
        (0.52, 0.32, 0.88, 0.49, 0.015),
        (0.52, 0.52, 0.63, 0.65, 0.015),
        (0.645, 0.52, 0.755, 0.65, 0.015),
        (0.77, 0.52, 0.88, 0.65, 0.015),
    ]},
    # S13: two columns - visitors who met it, and the holdout
    "layout7": {"16:9": [
        (0.52, 0.24, 0.63, 0.80, 0.03),      # taller: with FluidBuddha
        (0.70, 0.44, 0.81, 0.80, 0.03),      # shorter: without
    ]},
})

KEYFRAMES.update({
    "K6": {"refs": ["K3", "layout2"], "prompt": f"""
{KEEP} {NIGHT}
The second reference image is a layout mask (grey rounded rectangles). The glass has re-formed
into a new floating arrangement placed EXACTLY where the grey shapes are: a tall narrow panel on
the right (a conversation column), a wide card at top-left of the arrangement (a price card), and
below it three small square nodes in a row joined by two short thin glass bars (a flowchart).
Clear liquid glass with warm gold edges, glowing softly. {BLANK} The pool below reflects the glow,
with thin streams of liquid still connecting the forms to it. {LEFT}"""},
    "K7": {"refs": ["K6", "layout3"], "prompt": f"""
{KEEP} {NIGHT}
The second reference image is a layout mask. The glass now forms a tall column of four stacked
panels, like the sections of a web page, placed EXACTLY where the grey shapes are. A thin ring of
molten liquid gold runs around the third panel only, glowing brightly and highlighting it; the
other panels are dimmer. {BLANK} The pool below reflects the column. {LEFT}"""},
    "K8": {"refs": ["K7", "layout4"], "prompt": f"""
{KEEP} {NIGHT}
The second reference image is a layout mask. A single elegant glass card floats where the large
grey shape is, with a smaller rounded pill shape set into its lower part, glowing warm gold like a
button that has just been pressed. Directly below the card, a single small drop of liquid gold is
falling towards the pool. {BLANK} {LEFT}"""},
    "K9": {"refs": ["K8"], "prompt": f"""
{KEEP} {NIGHT}
An exploded view: the glass interface from the earlier scenes has separated into five thin
translucent glass layers floating one behind another in depth, evenly spaced, seen at a gentle
three-quarter angle so the gaps between the layers are visible: a full page panel at the back, a
glowing gold ring, a tall narrow conversation panel, a card, and a small gold drop at the front.
Each layer casts a soft glow onto the next. {BLANK} Placed in the centre-right of the frame. {LEFT}"""},
    "K10": {"refs": ["K8"], "prompt": f"""
{KEEP} {NIGHT}
Same world as the reference: the same warm near-black night background and dark floor, NO walls,
NO room, NO architecture, NO white surfaces anywhere. The glass card has melted away: only the same
round, organic puddle of liquid glass from the reference remains on the floor in the centre-right,
perfectly still like a mirror.
Floating in the darkness around and above it are about ten soft rectangular light panels, like
studio softboxes or blank glowing pages, at different depths. Their warm white light is reflected
in the liquid surface. One panel, above and behind the pool, is much brighter than the others and
its reflection shines gold in the liquid. The panels are completely blank: no text. {LEFT}"""},
    "K11": {"refs": ["K10"], "prompt": f"""
Keep the camera, composition, night background, puddle and panel positions exactly as in the
reference image. NO walls, NO room, NO white surfaces.
Now every light panel has gone dark and dim. With nothing to reflect, the liquid has lost its
shine: it is a flat, dull, matte grey, slumped low and lifeless, with no gold highlights at all.
The scene is almost colourless and quiet. {LEFT}"""},
    "K13": {"refs": ["K0", "layout6"], "prompt": f"""
Keep the camera, lighting, warm white background and pool exactly as in the first reference image
(daylight, no night). The second reference image is a layout mask. The pool has risen and
crystallised into a small, neat, floating website made of clear liquid glass with warm gold edges,
placed EXACTLY where the grey shapes are: a thin bar on top, a wide panel, and three small cards in
a row. A few tiny droplets are still falling into the pool around it, like rain. {BLANK} {LEFT}"""},
    "K14": {"refs": ["K13", "layout7"], "prompt": f"""
Keep the camera, lighting, warm white background and pool exactly as in the first reference image.
The second reference image is a layout mask. The glass has re-formed into two tall glass columns
standing on the pool, placed EXACTLY where the grey shapes are: both columns sit in the RIGHT half
of the frame (the left column starts just right of the frame's centre), and the whole left half of
the frame is empty white space. The columns are each filled with luminous liquid
gold up to its top: the left column clearly taller than the right one. Clean, calm, like a
beautiful bar chart made of liquid glass. {BLANK} {LEFT}"""},
    "K15": {"refs": ["K0"], "prompt": f"""
Keep the lighting and warm white background exactly as in the reference image (daylight).
The pool and every glass form have flowed together into one single, perfect drop of liquid
gold-glass resting on the floor near the bottom-right corner of the frame, about the size of a
pearl, with a soft gold caustic glow beneath it. The rest of the frame is empty white space."""},
})

SHOTS.update({
    "S05": {"from": "K4", "to": "K3", "seconds": 6,
            "prompt": "The frost melts: warm gold light spreads back through every frozen glass panel from the inside, "
                      "the ice crystals dissolve and the glass becomes clear and liquid again, glowing warmly."},
    "S06": {"from": "K3", "to": "K6", "seconds": 10,
            "prompt": "The glass interface melts and re-forms: liquid rises from the pool and from the old panels and "
                      "crystallises into a tall conversation panel, a price card and three small nodes joined by thin bars. "
                      "Smooth, viscous, elegant."},
    "S07": {"from": "K6", "to": "K7", "seconds": 8,
            "prompt": "The forms flow downward into a tall column of stacked page sections, and a thin ribbon of molten "
                      "gold runs down the column and wraps into a glowing ring around the third section."},
    "S08": {"from": "K7", "to": "K8", "seconds": 10,
            "prompt": "The column gathers into a single glass card with a pill button. The button glows as if pressed, "
                      "and a small drop of liquid gold separates from the card and falls towards the pool."},
    "S09": {"from": "K8", "to": "K9", "seconds": 8,
            "prompt": "The glass separates into thin layers that drift apart in depth, revealing an exploded view; "
                      "the view turns gently to a three-quarter angle.",
            "camera": "Camera: a slow, smooth orbit of about 20 degrees to the right, no other movement."},
    "RA": {"from": "K9", "to": "K9", "seconds": 6,
           "prompt": "A seamless loop: the floating glass layers breathe very gently, rising and falling a few "
                     "millimetres, their gold glow pulsing softly. The last frame is identical to the first."},
    "S10A": {"from": "K9", "to": "K10", "seconds": 8,
             "prompt": "The layers melt back down into a perfectly still mirror pool, and around it soft blank light "
                       "panels fade up in the darkness, reflected in the liquid; one panel brightens and its reflection "
                       "shines gold.",
             "camera": "Camera: a slow pull back to a wider view."},
    "S10B": {"from": "K10", "to": "K11", "seconds": 6,
             "prompt": "One by one the light panels dim and go dark. With nothing to reflect, the liquid loses its shine, "
                       "turns flat dull grey and slowly slumps lower."},
    "S11": {"from": "K11", "to": "K0", "seconds": 8,
            "prompt": "Dawn: soft warm daylight slowly floods the scene, the dark background brightens to a warm white "
                      "seamless sweep, the floating panels fade away, and the liquid recovers its clear, golden shine as "
                      "it settles into a calm puddle."},
    "S12": {"from": "K0", "to": "K13", "seconds": 10,
            "prompt": "A single gold drop falls into the pool, then a gentle rain of tiny droplets follows; the pool "
                      "swells and rises, crystallising into a small, neat glass website."},
    "S13": {"from": "K13", "to": "K14", "seconds": 8,
            "prompt": "The small website melts and re-forms into two tall glass columns that fill up with luminous liquid "
                      "gold from the bottom; the left column rises higher than the right."},
    "S14": {"from": "K14", "to": "K15", "seconds": 10,
            "prompt": "Everything flows together: the columns and the pool melt and gather into one single drop of liquid "
                      "gold-glass, which rolls gently to rest near the bottom-right corner of the frame."},
    "RB": {"from": "K15", "to": "K15", "seconds": 6,
           "prompt": "A seamless loop: the single gold drop rests and breathes very gently, its caustic glow pulsing "
                     "softly. Nothing else moves. The last frame is identical to the first."},
})
