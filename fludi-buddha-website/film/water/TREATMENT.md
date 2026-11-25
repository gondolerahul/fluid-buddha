# The water film: treatment

The background film of the General site (`/`), made in code in the **Impasto Oil Painting** style of
[Lemo-Opuscar](https://github.com/lemomo-ai/lemo-opuscar) (`styles/impasto/STYLE.md`). Every frame
is painted from palette-knife strokes on the graphics card; there is no video model and no footage.

## The brief, and how it was refined

The brief: water's journey from cloud to vessel, as one continuous, meditative take, ending on the
FluidBuddha name. Five refinements made it fit the site and the medium:

1. **Only the brand's three tubes of paint.** The Buddha Cognitive Lab design system rules out cool or
   blue imagery ("warm, never cool/blue"; gold, warm near-black, warm white). So the blue glacier and
   the ocean blues of the brief are painted in ink, paper white and gold: ice is warm white with amber
   light inside its cracks, the sea is ink with a path of gold. Every colour in the film is a mix of
   `#0a0908`, `#fffdf9` and `#edab48` (`lib.js`), and each stroke's small colour shift may only warm.
2. **One subject, one turn.** The subject is water; the turn is that it is shapeless all the way
   down the mountain, and at the end it takes the shape of what holds it. That is also the site's
   claim (the page fits the visitor), so the vessel is placed under the chapter "The page changes to
   fit the kind of visitor".
3. **Transitions made by the knife.** The style forbids dissolves (two layers of ridges turn to mud).
   Each change of state is a paint-over: the vapour is laid in from the heart of the cloud outwards,
   the avalanche pours off the ridge and the glacier is laid in under it, the spray of the falls is a
   scumble that clears to the sea, the camera slips under the surface along a waterline.
4. **Gaps in the brief closed.** The brief's camera notes mention an avalanche and its numbering
   skips the delta. The avalanche is kept, as the bridge from the range to the glacier ("the rushing
   snow settles into a vast glacier"); the delta is dropped, and the spray of the falls clears onto
   the open sea instead, so water becomes sea without a cut.
5. **Silent on the page.** On the website the film is scrubbed by scrolling, so it has no sound:
   browsers block sound that starts by itself, and a score cannot follow a scroll. The score and
   water sounds of the brief belong to a stand-alone cut of the film (not made yet; see "Sound").

## Three structures considered

| | Structure | Why not, or why |
|---|---|---|
| A | **One journey down** (chosen): cloud, crystal, range, ice, stream, river, falls, sea, depth, vessel | The brief's own order. Each state hands its material to the next, so the transitions carry the story. |
| B | Before and after: the same bowl, empty at the start and full at the end, with the journey as a memory between | Strong rhyme, but it spends the opening on an empty bowl instead of the hook of the dawn sky. |
| C | A countdown of states (vapour, crystal, ice, water) as four stills that the knife repaints | Clear, but static: it loses the continuous camera the brief asks for. |

**Logline.** A single drop of water falls from a dawn sky, travels the whole of the land, and at the
end comes to rest in a bowl, taking its shape exactly.
**Arc.** Weightless (clouds) → born (the crystal) → many (snowfall) → held (range, ice) → released
(meltwater, stream, river) → the leap (falls) → open (sea, depth) → at rest, in shape (the bowl) →
the name.

## Benchmark

- **Learn:** the long single take and slow, motivated camera of nature documentaries that follow one
  element (composition by layers, one move per shot, the breath before a reveal); the value structure
  of palette-knife landscape painting (three values per plane, hard edges only at the focus).
- **Don't take:** any specific film's shots, music or framing; no real places or landmarks.

## Shot list and timeline

Film time runs 0 to 90 s (`film.js`, object `T`). On the site it is scrubbed by scroll (540 frames).

| # | Time (s) | Shot and camera | Why | Site chapter |
|---|---|---|---|---|
| 1 | 0 to 5.2 | Wide over a sea of cloud at dawn, two towers catching first light. Slow glide forward | The hook: a quiet, vast, warm first frame under the hero copy | Hero |
| 1b | 5.2 to 9.7 | The camera dives into the nearest cloud | "Drift inside a cloud" | |
| 2 | 8.5 to 16.2 | Inside the cloud the vapour is laid in from the centre out; a crystal forms arm by arm as the camera pushes in; a beat of stillness, its tips catch gold | The birth of the subject; the stillness lets it register | "A question" |
| 3 | 16.2 to 23.4 | Pull back: the cloud is scraped away around the crystal, countless flakes fall through open sky; tilt down with them to the range | Scale revealed from one to many | |
| 4 | 23.4 to 31 | High crane forward over the peaks, descending towards one sharp ridge | The land that will hold the water | "It answers out loud" |
| 4b | 30.2 to 33 | The avalanche: snow pours off the ridge and fills the frame | The energetic bridge; snow becomes ice | |
| 5 | 31.6 to 40 | A glacier valley from above; slow sideways dolly; a pulse of light runs down the ice; the camera finds meltwater in a crack | Ice, and the first sign of water | "It draws charts" |
| 6 | 39.2 to 46 | Low tracking shot along a stream winding between stones towards the camera | Intimate scale after the vast | "It opens the right page" |
| 7 | 46.2 to 51.6 | Drone view of the river through the land; it rises and pulls back | The path revealed | |
| 7b | 51.4 to 56 | Skimming low over the river on a path of gold, towards the edge | The approach | "It books the meeting" |
| 8 | 55.6 to 61.5 | The falls: tilt down beside the curtain; the spray rises and fills the frame | The leap; the energetic peak | |
| 9 | 61.6 to 66.5 | The spray clears on the open sea; glide low towards the low sun | Water becomes sea; light rising | |
| 10 | 66.2 to 71.2 | The camera slips under: the waterline climbs the frame; shafts of light, motes, rising air | The quiet depth | |
| 11 | 71.2 to 78.6 | A clear stream pours into a white bowl with a gold rim; the camera arcs up and round; the water stills | Water takes shape | "It fits" |
| 12 | 78.6 to 84.4 | Close on the still water: a net of light on the bowl's floor; one ripple crosses and gathers it | The finish the brief asks for | "For you" |
| 12b | 84.4 to 90 | The camera eases back to the bowl on the dark, and the name is laid in by the knife | The end card | "Measure it" |

Camera moves used: glide, dive (push), push-in, pull-back, tilt, crane, sideways dolly, tracking,
drone rise, skim, tilt down, glide, sink, arc, macro push, ease back.

## Light

A gradual rise in light across the journey: first light under the cloud (shot 1), morning over the
range, full morning on the river, a low sun on the sea, the light of a quiet room at the end. Gold is
kept for light only (the dawn, the crests, the light inside ice, glitter, caustics, the rim, the name).

## Sound (for a stand-alone cut)

Not produced: the site film is silent (see refinement 5). If a stand-alone cut is wanted, the plan is:
a solo cello and harp in D, entering on the crystal; a real silence before the avalanche and before
the slip under; the falls as the one loud moment; foley of wind, a crystal "tick", the avalanche hiss,
running water, the pour, one water drop for the ripple. The style's sound palette
(`STYLE.md` §7) applies.

## Title design

The name is the brand's own logotype face (Roblox, from `brand/fonts`) in the logo's gold gradient,
laid in left to right by the knife, under the bowl. No other text is drawn into the film: the site's
copy is HTML beside it.

## Build

From `fludi-buddha-website/`:

```bash
node film/water/render.mjs sheet 0 90 2 --cols 8      # contact sheet of the whole film
node film/water/render.mjs frames --n 540             # the site's frames, PNG, to film/out/water/frames
.venv/Scripts/python film/water/export.py             # WebP for the site: web/public/film/water/960 and /512
node film/water/render.mjs video --fps 24             # a review cut, film/out/water/water.mp4 (needs ffmpeg)
```

`film/water/index.html?t=12.5` shows one moment in a browser; `?play=1` plays it.
