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
