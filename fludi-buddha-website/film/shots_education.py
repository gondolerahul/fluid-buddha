"""Shots for the Education world's scroll film (docs/marketing-docs/WebsitePlan.md §8).

The only film with people in it. Three people: a student of about nineteen, a parent and a
counsellor. They are seen from behind, in profile or at mid-distance, make small movements only,
and never speak to the camera.

Run from fludi-buddha-website/:
  .venv/Scripts/python film/pipeline.py seed --world education
  .venv/Scripts/python film/pipeline.py keyframes --world education
  .venv/Scripts/python film/pipeline.py clips --world education --res 360p     # drafts
  .venv/Scripts/python film/pipeline.py stitch --world education --res 360p --fps 12

Four keyframes are the approved style frames (K0 = E1, K1 = E2, K7 = E6, K9 = E7).
A shot marked "cut" starts a new scene; the stitch cross-fades into it.

  shot  keyframes   seconds  chapter of the page
  S1    K0 -> K1    6        hero, then "11 pm. A student is on your website"
  S2    K1 -> K2    4        "They ask in Hindi. It answers in Hindi"
  S3    K3 -> K4    6  cut   "It puts programmes and fees side by side"
  S4    K4 -> K5    6        "It walks them through your programmes"
  S5    K5 -> K6    4        "They say haan. It sends the application-fee link"
  S6    K7 -> K8    6  cut   "The student sends a summary to their parents"
  S7    K9 -> K10   6  cut   "9 am. Your counsellor has the lead"
  S8    K11 -> K12  6  cut   "Start before admission season"
"""

IMAGE_MODEL = "gemini-3-pro-image"
VIDEO_MODELS = ["gemini-omni-flash-preview"]

SEED = {"K0": "E1", "K1": "E2", "K7": "E6", "K9": "E7"}

STYLE = """
Visual style (keep identical in every frame): photoreal cinematic still from a warm, quiet
family drama set in a middle-class Indian home and a university office. Natural, candid and
unposed. Soft warm practical light, cream walls, warm wood, muted fabrics, gentle golden
highlights, no blue or cold tones. 35mm lens, shallow depth of field, fine natural skin texture.
People are seen from behind, in profile or at mid-distance, and never look at the camera.
Any phone or laptop screen shows only soft glowing abstract shapes of warm light.
The picture fills the whole frame from edge to edge. The left third of the frame is calm,
plain and uncluttered.
Strictly no readable text, no letters, no numbers, no logos, no watermarks.
""".strip()

CLIP_RULES = ("People move only a little, slowly and naturally; nobody looks at the camera and nobody speaks to it. "
              "Faces, hair, clothes and the room stay exactly the same for the whole shot. "
              "No readable text, no letters, no numbers, no logos, no captions. "
              "Silent: no music, no voices, no sound effects.")

LAYOUTS = {}

PHONE = ("An extreme close-up, from above and behind the student's right shoulder, of the smartphone held "
         "upright in the student's hand over the open notebooks on the wooden desk, in the warm light of the "
         "brass desk lamp. The same kurta sleeve and the same phone as in the reference image. The hand is the "
         "slim, smooth, young hand of a nineteen-year-old. At the right edge of the frame, the out-of-focus edge "
         "of the student's cheek and short dark hair: a smooth, young, clean-shaven face, no beard, no stubble. "
         "The phone fills the centre and right of the frame; its screen is large, sharp and faces the camera. "
         "The left third of the frame is the softly blurred desk and dark room.")

KEYFRAMES = {
    "K2": {"refs": ["K1"], "prompt": """
Keep everything exactly as in the reference image: the same student, hair, kurta, room, lamp,
camera position and framing. Only two things have changed. The student has lowered the phone a
little and is now looking at its screen, listening, with a slight smile. And the phone screen is
brighter: one of its soft rectangles glows a strong warm gold, and a small gentle wave of light
runs across the screen. The glow lights the student's cheek and fingers more than before."""},
    "K3": {"refs": ["K1"], "prompt": PHONE + """
On the screen, on a cream background: three plain vertical columns of soft warm light standing
side by side like the columns of a comparison table, each made of four or five blank rounded
blocks, all the same height. Under them is one thin horizontal line with a small round gold knob
at its left end, like a slider. No writing anywhere on the screen."""},
    "K4": {"refs": ["K3"], "prompt": """
Keep everything exactly as in the reference image: the same hand, phone, desk, light, camera
position and framing. Only the screen has changed. All three columns are still there, side by
side, each still made of blank rounded blocks. The middle column is now a brighter, stronger gold
than the two beside it and its lowest block is taller, and the small round gold knob has moved
to the right end of the thin line. The student's thumb rests near the knob. No writing
anywhere on the screen."""},
    "K5": {"refs": ["K4"], "prompt": """
Keep everything exactly as in the reference image: the same hand, phone, desk, light, camera
position and framing. Only the screen has changed. It now shows a simple page made of blank
blocks of soft warm light: one wide block at the top and three smaller blocks in a row beneath
it. The third small block, on the right, has a thin bright gold outline around it and glows more
than the others, as if it is being pointed out. No writing anywhere on the screen."""},
    "K6": {"refs": ["K5"], "prompt": """
Keep everything exactly as in the reference image: the same hand, phone, desk, light, camera
position and framing. Only the screen has changed. It now shows one single rounded card of warm
cream light in the middle of the screen, and in the centre of the card a gold circle with a
simple gold tick mark inside it. Nothing else is on the screen. The student's thumb has just
lifted away from the card. No writing anywhere on the screen."""},
    "K8": {"refs": ["K7"], "prompt": """
Keep everything exactly as in the reference image: the same two people, clothes, sofa, lamp,
room, camera position and framing. Only small things have changed. The parent has lifted her
eyes from her phone and turned her head a little towards the student with a warm, approving
smile; she holds the phone a little lower. The student has leaned in slightly closer and smiles
back. Both are still seen from the side. Neither looks at the camera."""},
    "K10": {"refs": ["K9"], "prompt": """
Keep everything exactly as in the reference image: the same counsellor, clothes, desk, laptop
seen from behind, window, plant, camera position and framing. Only small things have changed.
She has set the steel cup of tea down on the desk beside the laptop and leans a little towards
the laptop, reading it with interest and a slight smile, one hand resting near the keyboard. A
soft warm glow from the laptop screen lights her face. We still see only the plain back of the
laptop lid, never the screen. She does not look at the camera."""},
    "K11": {"refs": ["K9"], "prompt": """
The same admissions office and the same warm morning light as in the reference image, but now
with no person in the frame. A paper wall calendar hangs on the cream wall in the right half of
the frame, beside the window with thin curtains, with the small potted plant on a shelf below it.
The calendar page is a plain grid of small empty squares with nothing printed in them: no
numbers, no words. A ring has been drawn around one row of the grid in gold marker pen.
Sunlight through the curtains falls across the wall and the calendar. The left half of the frame
is the softly lit cream wall, calm and empty."""},
    "K12": {"refs": ["K11"], "prompt": """
The same wall, calendar, window, curtains, plant and morning light as in the reference image.
Exactly the same composition, with the camera only a little closer to the calendar, so the
calendar, the window and the plant are all a little larger and stay in the same places. The ring
around one row of the grid is drawn by hand in gold marker ink, flat on the paper like any pen
mark: it does not glow, it gives off no light and it does not float. The grid of small empty squares still has nothing printed in it: no numbers, no words. The
left third of the frame is the softly lit cream wall, calm and empty."""},
}

STILL = "Camera: locked off, perfectly still."
SHOTS = {
    "S1": {"from": "K0", "to": "K1", "seconds": 6,
           "camera": "Camera: one slow, smooth move forward and to the right, ending close behind the student's shoulder.",
           "prompt": "Night in a quiet bedroom. The student sits at the desk and slowly raises the smartphone from "
                     "the desk towards their mouth, as if about to ask it a question. The phone's glow grows on "
                     "their cheek and fingers. The lamp light is steady. Calm and unhurried."},
    "S2": {"from": "K1", "to": "K2", "seconds": 4, "camera": STILL,
           "prompt": "The student, seen in soft profile from behind, holds the phone near their mouth for a moment, "
                     "then lowers it a little and looks at the screen, listening, with a slight smile. The phone "
                     "screen grows brighter: one soft rectangle turns a strong warm gold and a gentle wave of light "
                     "runs across the screen. The student's mouth is not shown speaking."},
    "S3": {"from": "K3", "to": "K4", "seconds": 6, "camera": STILL, "cut": True,
           "prompt": "Only the phone screen and the thumb move. The student's thumb slides the small round gold knob "
                     "slowly along the thin line from the left end to the right end. As it moves, the middle column "
                     "grows brighter and turns a stronger gold, and one of its blocks grows larger. The hand, the "
                     "phone and the desk stay still."},
    "S4": {"from": "K4", "to": "K5", "seconds": 6, "hold": 1, "camera": STILL,
           "prompt": "Only the phone screen moves. The three columns and the slider fade smoothly and rearrange "
                     "into a simple page: one wide block on top and three smaller blocks in a row beneath it. A thin "
                     "gold outline appears around the first small block, moves to the second, then settles around "
                     "the third, which glows. The hand, the phone and the desk stay still."},
    "S5": {"from": "K5", "to": "K6", "seconds": 4, "hold": 1.5, "camera": STILL,
           "prompt": "Only the phone screen and the thumb move. The blocks on the screen fold together into one "
                     "single rounded card in the middle of the screen. The student's thumb taps the card once and "
                     "lifts away, and a gold circle with a simple tick mark draws itself in the centre of the card. "
                     "The hand, the phone and the desk stay still."},
    "S6": {"from": "K7", "to": "K8", "seconds": 6, "camera": STILL, "cut": True,
           "prompt": "A quiet family living room in the evening. The parent, sitting on the sofa in profile, reads "
                     "her phone for a moment, then slowly lifts her eyes and turns her head a little towards the "
                     "student with a warm, approving smile. The student, standing beside the sofa, leans in slightly "
                     "and smiles back. Small, natural movements only. Nobody speaks."},
    "S7": {"from": "K9", "to": "K10", "seconds": 6, "camera": STILL, "cut": True,
           "prompt": "Morning in a bright admissions office. The counsellor takes a small sip of tea, sets the steel "
                     "cup down on the desk beside the laptop, and leans a little towards the laptop, reading with "
                     "interest and a slight smile. A soft warm glow from the laptop screen lights her face. The "
                     "curtains move very slightly in the light. We never see the laptop screen."},
    "S8": {"from": "K11", "to": "K12", "seconds": 6, "cut": True,
           "camera": "Camera: one very slow, smooth move forward towards the calendar, at a constant speed. "
                     "It only ever moves forward: it never stops, never pulls back and never zooms out.",
           "prompt": "An empty office wall in morning light. The sunlight through the thin curtains shifts gently "
                     "across the wall and the paper calendar. The ring drawn in gold marker ink around one row of the "
                     "grid stays flat on the paper and never glows. The curtains move very slightly. Nothing else moves. The "
                     "calendar grid stays blank: no numbers, no words."},
}
