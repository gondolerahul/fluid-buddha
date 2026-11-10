# FluidBuddha film pipeline

Produces the scroll-driven liquid film described in
[`docs/marketing-docs/WebsiteConcept.md`](../../docs/marketing-docs/WebsiteConcept.md) §8–9.

## How it works

1. **Layout masks.** `shots.py → LAYOUTS` are the exact shapes the liquid must settle into, so
   the website's HTML can later sit precisely on the glass forms.
2. **Keyframes.** `gemini-3-pro-image` renders each join between shots (K0, K1, …) in the film's
   material and light. Each keyframe uses the previous one as a reference for continuity.
3. **Clips.** Gemini Omni interpolates from one keyframe to the next (3–10 s per shot), so every
   clip ends where the next begins.
4. **Stitch.** The clips are joined into `film.mp4` (no audio, short keyframe interval for
   scrubbing), frames are extracted at 24 fps, and a **seam check** measures every join.

## Run (from `fludi-buddha-website/`)

```bash
.venv/Scripts/python film/pipeline.py masks
.venv/Scripts/python film/pipeline.py keyframes            # or: keyframes K2 K3 --force
.venv/Scripts/python film/pipeline.py clips --res 360p     # drafts; finals: --res 1080p
.venv/Scripts/python film/pipeline.py stitch
```

The API key is read from `fludi-buddha-website/.env` (`GEMINI_API_KEY`, git-ignored). Every
request is logged in `out/manifest.json` (model, prompt, references, output) so any shot can be
remade. `film/preview.html` scrubs the stitched frames by scroll, with the site's copy on top.

## Status (6 November 2026)

| Item | State |
|---|---|
| Shots generated | All 14 shots plus both loops (S01–S14, RA, RB): 17 clips, 16:9, 360p drafts, about 2 min 13 s, 3,182 frames |
| Keyframes | 14 (K0–K4, K6–K11, K13–K15). K0 is reused as the dawn end of S11; K3 is reused as the thaw end of S05. |
| Seams | All 16 joins are under the 4.0 threshold (1.1–2.5) |
| Video model | `gemini-omni-flash-preview`. The 1.2 and 1.1 Flash IDs return "model not found" for this API key, so the pipeline falls back to the preview model automatically. |
| Preview | `film/preview.html`: scroll-scrubbed film with every chapter's copy, a chapter index, and the day/night switch |

### Issues to fix in the final renders

| Shot | Issue |
|---|---|
| S04 | K4's framing sits slightly closer than K3, so the freeze has a gentle push-in. Lock the framing. |
| S10B | The light panels flicker (dim, bright, dim) instead of fading out once. |
| S12 | Mid-shot, the pool swells and the camera seems to zoom before settling. Shorten the clip or add a mid keyframe. |
| S11 | Ghosted panels are visible for a moment on the white background during dawn. Acceptable, but cleaner with a mid keyframe. |
| All | 9:16 mobile versions are not made yet. |

## Notes for the full run

- Ask Google Cloud to enable `gemini-omni-1.2-flash` on the project; the preview model ID is
  scheduled for retirement. The pipeline already tries 1.2 first.
- Interpolation accepts 3–10 s only; keep every shot within that.
- Generated video can't render text, so frames contain no words. All copy is HTML.
- 9:16 mobile versions: `--aspect 9:16` for masks, keyframes and clips.
