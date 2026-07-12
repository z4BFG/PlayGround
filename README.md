# Akina Track — Initial D lore & 3D-model reference

Research and starter assets for building a 3D model of the **Mt. Akina (秋名)**
downhill course from *Initial D* (based on the real **Mt. Haruna**, Gunma Prefecture).

## Contents

| Path | What it is |
|---|---|
| [`docs/akina-track-lore.md`](docs/akina-track-lore.md) | Lore research + how to translate it into geometry, materials and scenery |
| [`docs/akina_plan_preview.svg`](docs/akina_plan_preview.svg) | Top-down plan-view preview of the generated layout |
| [`data/akina_track_spec.json`](data/akina_track_spec.json) | Machine-readable track spec: 898-point centerline (x/y/z), per-corner radius, gradient, banking, gutter flags |
| [`scripts/generate_akina_spec.py`](scripts/generate_akina_spec.py) | Regenerates the track spec from the parametric sector definitions |
| [`scripts/preview_akina.py`](scripts/preview_akina.py) | Renders the plan-view SVG from the spec |
| [`web/`](web/) | **Interactive three.js 3D model** of the course (see below) |

## three.js 3D viewer

`web/index.html` builds the full course in 3D from `data/akina_track_spec.json`:
the road ribbon (crown + inside drainage gutters on the hairpins), cliff-side
guardrails, cut/cliff embankments, forest, Lake Akina at the start, and an
AE86-style car that drives the downhill with a chase camera. A dusk/night look
to match Initial D's battles.

- **Controls:** mouse to orbit/zoom · **D** to toggle the chase camera ·
  `?t=<index>` in the URL jumps to and pauses at a point on the centerline.
- **Fully offline:** three.js r160 is vendored in `web/vendor/` (no CDN/network).

Open it either way:

```bash
# simplest — just open the file
xdg-open web/index.html            # or double-click it

# or serve it (any static server works)
python3 -m http.server -d web 8099   # then visit http://localhost:8099/
```

The track data is embedded in `web/track_data.js`. If you change the layout,
regenerate it:

```bash
python3 scripts/generate_akina_spec.py   # -> data/akina_track_spec.json
python3 scripts/embed_track.py           # -> web/track_data.js  (viewer reads this)
```

## Quick start

```bash
python3 scripts/generate_akina_spec.py   # -> data/akina_track_spec.json
python3 scripts/preview_akina.py         # -> docs/akina_plan_preview.svg
```

Then sweep a ~6 m road cross-section (with the inside drainage gutter on the
hairpins) along the `centerline` waypoints in the JSON to build the road mesh,
cut it into a heightfield, and scatter forest + guardrails along the verges.
See the lore doc for the full modeling recipe and sources.

> The layout is a **representative approximation** that preserves the course's
> character (five gutter hairpins, sweepers, gradient) — not a surveyed GPS track.
