# Akina (秋名) — Lore & Reference for a 3D Track Model

Research notes on the *Initial D* course **Mt. Akina (秋名山)** compiled specifically
to drive the construction of a 3D model of the racing track. Everything below is
split into two layers:

1. **Canon / real-world facts** — what the manga, anime and the real mountain establish.
2. **Modeling interpretation** — how to translate those facts into geometry, materials
   and scenery for a 3D scene.

> ⚠️ Accuracy note: Akina is a *fictionalized* version of a real road. Distances,
> elevations and corner descriptions below are canon/real approximations, **not a
> surveyed centerline**. The companion file [`data/akina_track_spec.json`](../data/akina_track_spec.json)
> contains a *representative parametric layout* for modeling — it captures the
> character of the course (order, radius, banking, gradient of the key corners),
> not GPS-exact geometry.

---

## 1. What Akina actually is

| Aspect | Detail |
|---|---|
| In-universe name | **Mt. Akina / Akina Pass (秋名, Akina)** |
| Real-world basis | **Mt. Haruna (榛名山, Haruna-san)**, Gunma Prefecture, Japan |
| Real road | **Gunma Prefectural Route 33**, connecting Ikaho (base) ↔ Lake Haruna (top) |
| Home team | **Akina SpeedStars**; ace **Takumi Fujiwara** in a Toyota Sprinter Trueno **AE86** |
| Rival home mountain | **Mt. Akagi** (RedSuns) — based on the real Mt. Akagi |
| Summit elevation | ≈ **1,449 m** (Mt. Haruna peak) |
| Lake elevation | **Lake Akina / Lake Haruna ≈ 1,080 m** |
| Course length | ≈ **15 km** base ↔ lake (the *raced* section is the downhill portion of this) |
| Signature feature | **Five consecutive hairpins** + inside **drainage gutters** |

### Race direction — this matters for the model
In *Initial D*, the iconic battles are the **downhill** run:
**start at Lake Akina (top) → finish near the foot of the mountain** (in the story,
close to the Fujiwara family's **gas stand / gas station** in Ikaho).
When you lay out the track, treat the **lake end as the START** and the
**base/gas-stand end as the FINISH**. The uphill is the same road reversed.

---

## 2. Signature course features (the stuff a fan will check)

These are the elements that make a model read as "Akina" rather than a generic touge:

1. **The five consecutive hairpins** — the defining sequence. Tight-radius
   switchbacks stacked down the slope in a left-right-left rhythm, separated by
   short straights and flowing S-curves. This is where Takumi's legend is built.
2. **The drainage gutter (溝, "the gutter run")** — a real concrete/earth **drainage
   ditch runs along the inside edge of the hairpins**. Takumi's signature move drops
   the **inside front tire into the gutter** through a hairpin to hold a tighter,
   faster line. The gutter must be modeled as a distinct recessed channel on the
   **inside apex** of the hairpins, not just a texture.
3. **Guardrails** — continuous steel W-beam (Gr guardrail) on the outside (cliff)
   edge for most of the course; Takumi is known for drifting inches from them.
4. **Dense forest canopy** — the road is cut through thick deciduous/cedar forest.
   Trees crowd both edges, creating a **tunnel-of-trees** feel and heavy shade/dappled
   light. Very few open vistas except near the lake and a couple of overlooks.
5. **Narrow two-lane width** — roughly **one lane each way (~5.5–6.5 m total)**,
   no shoulder to speak of, faded center line. Blind corners are the norm.
6. **Elevation & gradient** — a sustained descent; combine long sweepers with the
   hairpin clusters. Net drop of a few hundred meters over the raced section.
7. **Landmarks** — Lake Akina and its shoreline/parking area at the top; a small
   **shrine/observation area**; the **gas stand** near the base; scattered vending
   machines / small pull-offs where spectators gather in the anime.

---

## 3. Recommended modeling approach

Build the road as a **swept profile along a 3D spline centerline**:

1. **Centerline spline** — place waypoints (see the JSON spec). Each waypoint carries
   `x, y (elevation), z`, plus per-corner metadata (radius, banking, gradient).
2. **Road cross-section (profile)** swept along the spline:
   - Carriageway: ~6 m wide, slight crown (camber) for drainage.
   - **Inside gutter**: ~0.3–0.5 m wide, ~0.15–0.25 m deep recessed channel, present
     through the hairpins (flag `gutter_inside: true` on those segments).
   - Outside edge: guardrail line offset ~0.5 m beyond the asphalt.
3. **Terrain**: generate a heightfield/mesh around the spline. Cut the road into the
   slope — **fill on the inside, drop-off + guardrail on the outside** of each corner,
   consistent with a mountain shelf road.
4. **Scenery scatter**: instance trees densely along both verges, thinning at the lake
   and overlooks. Add guardrails as instanced W-beam segments following the outside offset.
5. **Materials**:
   - Asphalt: dark, slightly worn, faint center line, tire-marked apexes.
   - Gutter: concrete/earth channel material.
   - Guardrail: galvanized steel.
   - Foliage: mixed cedar + deciduous; ground cover / leaf litter on verges.
6. **Lighting**: heavy canopy shade with dappled highlights; the anime's most famous
   races are at **night**, so plan for a night-lighting pass (headlight cones, cool
   ambient, sparse reflectors on guardrails).

### Scale & orientation conventions used in the spec
- Units: **meters**. `y` = up (elevation). Model runs top→base along increasing index.
- The provided layout is compressed to a **~5.5 km representative raced section**
  (the memorable, frequently-raced stretch), not the full 15 km road — this keeps the
  model tractable while preserving corner character. Scale up if you want the full road.

---

## 4. Segment breakdown (representative)

The JSON spec encodes these sectors top → base:

| Sector | Character | Notes for modeling |
|---|---|---|
| S0 Lakeside start | Flat, open, gentle | Lake Akina, parking/shrine, start marker |
| S1 First plunge | Fast sweepers, gradient steepens | Establish the descent, tree tunnel begins |
| S2 The Five Hairpins | 5 stacked switchbacks | **Gutters on inside apexes**, guardrails outside |
| S3 Mid S-curves | Flowing esses between hairpin clusters | Rhythm section, camber changes |
| S4 High-speed section | Long straights + fast kinks | Where cars top out; slipstream battles |
| S5 Final descent to base | Tightening turns to the foot | Ends near the gas stand / town edge |

---

## 5. Sources

- [Akina — Initial D Wiki (Fandom)](https://initiald.fandom.com/wiki/Akina)
- [Gutter Techniques — Initial D Wiki (Fandom)](https://initiald.fandom.com/wiki/Gutter_Techniques)
- [Takumi Fujiwara's Toyota AE86 — Initial D Wiki (Fandom)](https://initiald.fandom.com/wiki/Takumi_Fujiwara's_Toyota_AE86)
- [Mount Akina: The Actual Initial D Pass in Gunma (Mt Haruna)](https://samuraicarjapanjdm.jp/mount-akina-initial-d-real-location-japan/)
- [Mount Akina Drifting: The Real Touge Roads Behind Initial D](https://samuraicarjapanjdm.jp/mount-akina-drifting-initial-d-touge-guide/)
- [Mount Akina Touge: Drive the Initial D Road (2026 Map)](https://samuraicarjapanjdm.jp/mount-haruna-initial-d-real-mount-akina/)
- [Mount Akina in Assetto Corsa: Racing Initial D's Touge](https://samuraicarjapanjdm.jp/mount-akina-assetto-corsa-initial-d-touge/)
- [Akina Mountain Initial D: Real Location Guide — Japan Uncharted](https://japanuncharted.com/gunma/mountain/akina-mountain-initial-d)
