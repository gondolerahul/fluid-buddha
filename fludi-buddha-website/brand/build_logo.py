"""Build the FluidBuddha logo lockups.

The FluidBuddha lockup is a sibling of the Hire Buddha lockup:
  * the dotted-B icon is taken unchanged from the Hire Buddha lockup;
  * the second line "BUDDHA" is taken unchanged from the Hire Buddha wordmark;
  * the first line "FLUID" replaces "HIRE". Its I, U and D reuse the lockup's own
    hand-tuned glyphs; F and L are set in Roblox Black (the face the lockup is drawn in,
    verified by matching glyph widths) at the same cap height and tracking.

Outputs (in brand/logo/):
  logo-fluidbuddha-{gold,white,black,onblack}.svg            stacked lockup (primary)
  logo-fluidbuddha-horizontal-{gold,white,black,onblack}.svg one-line lockup (nav bars)
  logo-fluidbuddha.svg                                        = gold stacked
  favicon.svg                                                 = gold icon
"""
import re
from pathlib import Path

from fontTools.pens.boundsPen import BoundsPen
from fontTools.pens.recordingPen import RecordingPen
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.svgLib.path import parse_path
from fontTools.ttLib import TTFont

HERE = Path(__file__).parent
REF = HERE / "reference" / "logo-hire-buddha-gold.svg"
FONT = HERE / "fonts" / "RobloxFontBlack-x3y2j.ttf"
OUT = HERE / "logo"
OUT.mkdir(exist_ok=True)

ref = REF.read_text(encoding="utf-8")
icon_d, word_d = re.findall(r' d="([^"]+)"', ref)


def contours_of(d):
    rec = RecordingPen()
    parse_path(d, rec)
    out, cur = [], []
    for op, args in rec.value:
        if op == "moveTo" and cur:
            out.append(cur)
            cur = []
        cur.append((op, args))
    out.append(cur)
    return out


def bounds(contour):
    b = BoundsPen(None)
    for op, args in contour:
        getattr(b, op)(*args)
    return b.bounds


def draw(contour, pen):
    for op, args in contour:
        getattr(pen, op)(*args)


word = contours_of(word_d)
# Measured: contours 0-5 = "HIRE" (cap 29.9-131.8), 6-14 = "BUDDHA" (cap 172.0-274.0)
HIRE_I = [word[2]]
BUDDHA = word[6:15]
B_U = [word[9]]
B_D = [word[10]]
TOP_CAP, BASE = 29.9, 131.8
LINE_SHIFT = 172.0 - TOP_CAP  # BUDDHA line sits this far below the first line

font = TTFont(FONT)
gs, cmap, hmtx = font.getGlyphSet(), font.getBestCmap(), font["hmtx"]
SC = (BASE - TOP_CAP) / 702.0  # Roblox Black cap height is 702 units


def glyph_metrics(ch):
    g = cmap[ord(ch)]
    b = BoundsPen(gs)
    gs[g].draw(b)
    adv, _ = hmtx[g]
    return g, adv * SC, b.bounds[0] * SC, b.bounds[2] * SC


def build_word(text, x_left, line_dy=0.0):
    """Return SVG path data for `text`, first glyph's ink starting at x_left."""
    pen = SVGPathPen(None)
    first = glyph_metrics(text[0])
    x_pen = x_left - first[2]
    for ch in text:
        g, adv, xmin, xmax = glyph_metrics(ch)
        target_left = x_pen + xmin
        reuse = {"I": (HIRE_I, 0.0), "U": (B_U, -LINE_SHIFT), "D": (B_D, -LINE_SHIFT)}.get(ch)
        if reuse:  # the lockup's own hand-tuned glyph, moved into place
            cs, dy = reuse
            old_left = min(bounds(c)[0] for c in cs)
            t = TransformPen(pen, (1, 0, 0, 1, target_left - old_left, dy + line_dy))
            for c in cs:
                draw(c, t)
        else:  # Roblox Black outline, flipped into SVG space at the lockup's scale
            t = TransformPen(pen, (SC, 0, 0, -SC, x_pen, BASE + line_dy))
            gs[g].draw(t)
        x_pen += adv
    return pen.getCommands()


def commands(contours, dx=0.0, dy=0.0):
    pen = SVGPathPen(None)
    t = TransformPen(pen, (1, 0, 0, 1, dx, dy))
    for c in contours:
        draw(c, t)
    return pen.getCommands()


GRAD_ICON = ('<linearGradient id="fb-icon" x1="10.03" y1="206.98" x2="166.16" y2="186.64" gradientUnits="userSpaceOnUse"{xf}>'
             '<stop offset="0" stop-color="#fdc871"/><stop offset="0.26" stop-color="#edab48"/>'
             '<stop offset="0.54" stop-color="#ffefd8"/><stop offset="1" stop-color="#fdc871"/></linearGradient>')


def grad_word(x1, x2, y):
    return (f'<linearGradient id="fb-word" x1="{x1:.2f}" y1="{y:.2f}" x2="{x2:.2f}" y2="{y:.2f}" gradientUnits="userSpaceOnUse">'
            '<stop offset="0" stop-color="#fdc871"/><stop offset="0.34" stop-color="#edab48"/>'
            '<stop offset="0.74" stop-color="#ffefd8"/><stop offset="1" stop-color="#fdc871"/></linearGradient>')


FILLS = {  # (icon fill, wordmark fill) — mirrors the Hire Buddha variants
    "gold": ("url(#fb-icon)", "url(#fb-word)"),
    "white": ("#ffffff", "#ffffff"),
    "black": ("#0a0a0a", "#0a0a0a"),
    "onblack": ("#fdc871", "#ffffff"),
}


def svg(viewbox, icon_path, word_path, gx1, gx2, gy, variant, title, icon_scale=1.0):
    fi, fw = FILLS[variant]
    gi = GRAD_ICON.format(xf=f' gradientTransform="scale({icon_scale:.4f})"' if icon_scale != 1.0 else '')
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{viewbox}" role="img" aria-label="{title}">'
            f'<title>{title}</title><defs>{gi}{grad_word(gx1, gx2, gy)}</defs>'
            f'<path fill="{fi}" d="{icon_path}"/><path fill="{fw}" d="{word_path}"/></svg>\n')


# ---- stacked lockup: same canvas, icon and second line as Hire Buddha -------------
fluid = build_word("FLUID", x_left=127.6)
stack_word = fluid + commands(BUDDHA)
for v in FILLS:
    (OUT / f"logo-fluidbuddha-{v}.svg").write_text(
        svg("0 0 728.69 396.08", icon_d, stack_word, 127.67, 728.69, 151.9, v, "FluidBuddha"), encoding="utf-8")
(OUT / "logo-fluidbuddha.svg").write_text((OUT / "logo-fluidbuddha-gold.svg").read_text(encoding="utf-8"), encoding="utf-8")

# ---- horizontal lockup: icon, then FLUID BUDDHA on one line, vertically centred ----
# The icon is scaled down so the one-line wordmark stays legible at nav-bar heights:
# icon height = 2.1 x the cap height.
cap = BASE - TOP_CAP
ICON_S = (cap * 2.1) / 396.08
icon_h = 396.08 * ICON_S
_ip = SVGPathPen(None)
_it = TransformPen(_ip, (ICON_S, 0, 0, ICON_S, 0, 0))
for c in contours_of(icon_d):
    draw(c, _it)
icon_small = _ip.getCommands()
line_dy = (icon_h / 2 - cap / 2) - TOP_CAP  # centre the cap height on the icon
x0 = 157.4 * ICON_S + cap * 0.55            # a calm gap after the icon
h_fluid = build_word("FLUID", x_left=x0, line_dy=line_dy)
fluid_right = x0 + sum(glyph_metrics(c)[1] for c in "FLUID") - glyph_metrics("F")[2]
space = glyph_metrics("H")[1] * 0.42
b_left = min(bounds(c)[0] for c in BUDDHA)
b_right = max(bounds(c)[2] for c in BUDDHA)
h_buddha = commands(BUDDHA, dx=(fluid_right + space) - b_left, dy=-LINE_SHIFT + line_dy)
h_right = fluid_right + space + (b_right - b_left)
for v in FILLS:
    (OUT / f"logo-fluidbuddha-horizontal-{v}.svg").write_text(
        svg(f"0 0 {h_right:.2f} {icon_h:.2f}", icon_small, h_fluid + h_buddha, x0, h_right, icon_h / 2, v, "FluidBuddha", icon_scale=ICON_S),
        encoding="utf-8")

# ---- favicon: the dotted-B icon alone ---------------------------------------------
(OUT / "favicon.svg").write_text(
    f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="-60 0 277.4 396.08"><defs>{GRAD_ICON.format(xf="")}</defs>'
    f'<path fill="url(#fb-icon)" d="{icon_d}"/></svg>\n', encoding="utf-8")
print("written:", sorted(p.name for p in OUT.iterdir()))
