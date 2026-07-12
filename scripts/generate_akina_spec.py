#!/usr/bin/env python3
"""Generate a representative parametric centerline for the Akina downhill course.

This is NOT a surveyed GPS track. It is a modeling-oriented approximation that
preserves the *character* of Mt. Akina (Initial D): a lakeside start, a fast
plunge, five consecutive hairpins with inside drainage gutters, flowing esses,
a high-speed section, and a tightening final descent to the base.

Units: meters. Coordinate frame: x/z = horizontal plane, y = elevation (up).
Output: data/akina_track_spec.json
"""
import json
import math
import os

ROAD_WIDTH = 6.0          # carriageway width (two narrow lanes)
GUTTER_WIDTH = 0.4        # inside drainage channel width
GUTTER_DEPTH = 0.2        # inside drainage channel depth
CROWN = 0.08              # road crown/camber (center higher than edges)
GUARDRAIL_OFFSET = 0.5    # guardrail placed this far outside the asphalt edge

# Sector definitions: (name, character, length_m, drop_m, corners)
# corners: list of dicts describing turns to lay down within the sector.
# turn 'angle' is heading change in degrees (+ = left, - = right in plan view),
# 'radius' is corner radius in meters, 'hairpin'/'gutter' flags for modeling.
SECTORS = [
    {
        "id": "S0", "name": "Lakeside start", "character": "flat, open, gentle",
        "length": 400, "drop": 8,
        "corners": [
            {"angle": -25, "radius": 120, "hairpin": False, "gutter": False},
            {"angle": 30, "radius": 90, "hairpin": False, "gutter": False},
        ],
    },
    {
        "id": "S1", "name": "First plunge", "character": "fast sweepers, steepening",
        "length": 900, "drop": 70,
        "corners": [
            {"angle": -60, "radius": 70, "hairpin": False, "gutter": False},
            {"angle": 45, "radius": 55, "hairpin": False, "gutter": False},
            {"angle": -50, "radius": 60, "hairpin": False, "gutter": False},
        ],
    },
    {
        "id": "S2", "name": "The Five Hairpins", "character": "five stacked switchbacks",
        "length": 1300, "drop": 130,
        "corners": [
            {"angle": 165, "radius": 12, "hairpin": True, "gutter": True},
            {"angle": -168, "radius": 11, "hairpin": True, "gutter": True},
            {"angle": 170, "radius": 13, "hairpin": True, "gutter": True},
            {"angle": -166, "radius": 11, "hairpin": True, "gutter": True},
            {"angle": 168, "radius": 12, "hairpin": True, "gutter": True},
        ],
    },
    {
        "id": "S3", "name": "Mid S-curves", "character": "flowing esses",
        "length": 800, "drop": 55,
        "corners": [
            {"angle": 40, "radius": 45, "hairpin": False, "gutter": False},
            {"angle": -45, "radius": 40, "hairpin": False, "gutter": False},
            {"angle": 38, "radius": 48, "hairpin": False, "gutter": False},
            {"angle": -42, "radius": 42, "hairpin": False, "gutter": False},
        ],
    },
    {
        "id": "S4", "name": "High-speed section", "character": "long straights + fast kinks",
        "length": 1100, "drop": 60,
        "corners": [
            {"angle": -20, "radius": 150, "hairpin": False, "gutter": False},
            {"angle": 18, "radius": 160, "hairpin": False, "gutter": False},
            {"angle": -30, "radius": 100, "hairpin": False, "gutter": False},
        ],
    },
    {
        "id": "S5", "name": "Final descent to base", "character": "tightening turns to the foot",
        "length": 900, "drop": 75,
        "corners": [
            {"angle": 70, "radius": 30, "hairpin": False, "gutter": False},
            {"angle": -85, "radius": 22, "hairpin": False, "gutter": False},
            {"angle": 60, "radius": 28, "hairpin": False, "gutter": False},
            {"angle": -100, "radius": 18, "hairpin": True, "gutter": False},
        ],
    },
]

STEP = 6.0  # sample the centerline roughly every 6 meters


def build_centerline():
    """Walk the sectors, emitting evenly spaced centerline points with metadata."""
    points = []
    heading = math.radians(0.0)   # plan-view heading, radians
    x, z = 0.0, 0.0
    y = 1080.0                    # start at Lake Akina elevation (~1080 m)

    for sec in SECTORS:
        seg_len = sec["length"]
        drop = sec["drop"]
        n = max(1, int(seg_len / STEP))
        ds = seg_len / n
        grade = -drop / seg_len   # negative = descending

        # Distribute corners across the sector: each corner is a turn arc,
        # straights fill the remainder.
        corners = sec["corners"]
        # place corner "centers" at even fractions of the sector
        markers = {}
        if corners:
            for i, c in enumerate(corners):
                idx = int((i + 1) * n / (len(corners) + 1))
                markers[idx] = c

        for i in range(n):
            corner = markers.get(i)
            in_corner = False
            gutter = False
            hairpin = False
            radius = None
            banking = 0.0

            if corner:
                # apply the whole heading change of this corner over a short arc
                arc_pts = max(2, int((math.radians(abs(corner["angle"])) * corner["radius"]) / ds))
                # we approximate: turn happens across this single marker by rotating heading
                heading += math.radians(corner["angle"])
                in_corner = True
                gutter = corner["gutter"]
                hairpin = corner["hairpin"]
                radius = corner["radius"]
                # bank hairpins/tight corners slightly (positive = inside lower)
                banking = round(min(6.0, 250.0 / corner["radius"]), 2)

            x += math.cos(heading) * ds
            z += math.sin(heading) * ds
            y += grade * ds

            points.append({
                "i": len(points),
                "sector": sec["id"],
                "x": round(x, 2),
                "y": round(y, 2),
                "z": round(z, 2),
                "heading_deg": round(math.degrees(heading) % 360, 1),
                "grade_pct": round(grade * 100, 2),
                "corner": in_corner,
                "hairpin": hairpin,
                "radius_m": radius,
                "gutter_inside": gutter,
                "banking_deg": banking,
            })
    return points


def main():
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    points = build_centerline()
    total_len = round(sum(STEP for _ in points), 1)
    y_vals = [p["y"] for p in points]

    spec = {
        "name": "Akina Downhill (representative parametric layout)",
        "source_basis": "Initial D — Mt. Akina / real Mt. Haruna, Gunma Pref. (Route 33)",
        "disclaimer": "Approximate, modeling-oriented layout — NOT a surveyed/GPS track. "
                      "Captures course character (order, radius, gutters, gradient), not exact geometry.",
        "units": "meters",
        "axes": {"x": "east", "z": "north", "y": "up (elevation)"},
        "direction": "downhill: start = Lake Akina (top), finish = base near gas stand",
        "road": {
            "carriageway_width_m": ROAD_WIDTH,
            "crown_m": CROWN,
            "gutter_width_m": GUTTER_WIDTH,
            "gutter_depth_m": GUTTER_DEPTH,
            "guardrail_offset_m": GUARDRAIL_OFFSET,
            "guardrail": "outside (cliff) edge, continuous W-beam",
        },
        "stats": {
            "point_count": len(points),
            "approx_length_m": total_len,
            "elevation_top_m": max(y_vals),
            "elevation_base_m": round(min(y_vals), 1),
            "elevation_drop_m": round(max(y_vals) - min(y_vals), 1),
            "hairpin_count": sum(1 for p in points if p["hairpin"]),
            "gutter_apex_count": sum(1 for p in points if p["gutter_inside"]),
        },
        "sectors": [
            {"id": s["id"], "name": s["name"], "character": s["character"],
             "length_m": s["length"], "drop_m": s["drop"]}
            for s in SECTORS
        ],
        "landmarks": [
            {"name": "Lake Akina (Lake Haruna)", "at_sector": "S0", "note": "start, open water + parking/shrine"},
            {"name": "Five Hairpins", "at_sector": "S2", "note": "signature switchbacks with inside gutters"},
            {"name": "Gas stand / town edge", "at_sector": "S5", "note": "finish area near the base"},
        ],
        "centerline": points,
    }

    out = os.path.join(root, "data", "akina_track_spec.json")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(spec, f, indent=2, ensure_ascii=False)
    print(f"Wrote {out}")
    print(f"  points={len(points)} length~{total_len}m "
          f"drop~{spec['stats']['elevation_drop_m']}m hairpins={spec['stats']['hairpin_count']}")


if __name__ == "__main__":
    main()
