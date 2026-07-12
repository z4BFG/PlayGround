#!/usr/bin/env python3
"""Render a top-down (plan) preview SVG of the Akina centerline, colored by sector."""
import json
import os

COLORS = {
    "S0": "#4da3ff", "S1": "#39c46e", "S2": "#ff4d4d",
    "S3": "#ffb000", "S4": "#9b6bff", "S5": "#ff7ac2",
}
NAMES = {
    "S0": "Lakeside start", "S1": "First plunge", "S2": "Five Hairpins",
    "S3": "Mid S-curves", "S4": "High-speed", "S5": "Final descent",
}


def main():
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    with open(os.path.join(root, "data", "akina_track_spec.json"), encoding="utf-8") as f:
        spec = json.load(f)
    pts = spec["centerline"]

    xs = [p["x"] for p in pts]
    zs = [p["z"] for p in pts]
    minx, maxx, minz, maxz = min(xs), max(xs), min(zs), max(zs)
    pad = 60
    W = 900
    scale = (W - 2 * pad) / max(1e-6, (maxx - minx))
    H = int((maxz - minz) * scale + 2 * pad)

    def px(x): return pad + (x - minx) * scale
    def py(z): return H - (pad + (z - minz) * scale)  # flip so north is up

    # build polylines per sector
    segs = {}
    for p in pts:
        segs.setdefault(p["sector"], []).append(f"{px(p['x']):.1f},{py(p['z']):.1f}")

    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
             f'viewBox="0 0 {W} {H}">',
             f'<rect width="{W}" height="{H}" fill="#12161c"/>',
             f'<text x="{pad}" y="34" fill="#e8edf2" font-family="sans-serif" '
             f'font-size="20" font-weight="700">Akina Downhill — plan view (representative)</text>']

    for sid in ["S0", "S1", "S2", "S3", "S4", "S5"]:
        if sid in segs:
            parts.append(f'<polyline points="{" ".join(segs[sid])}" fill="none" '
                         f'stroke="{COLORS[sid]}" stroke-width="5" '
                         f'stroke-linejoin="round" stroke-linecap="round"/>')

    # hairpin/gutter apex markers
    for p in pts:
        if p["gutter_inside"]:
            parts.append(f'<circle cx="{px(p["x"]):.1f}" cy="{py(p["z"]):.1f}" r="6" '
                         f'fill="none" stroke="#ffffff" stroke-width="2"/>')

    # start & finish
    s, e = pts[0], pts[-1]
    parts.append(f'<circle cx="{px(s["x"]):.1f}" cy="{py(s["z"]):.1f}" r="8" fill="#4da3ff"/>')
    parts.append(f'<text x="{px(s["x"])+12:.1f}" y="{py(s["z"]):.1f}" fill="#e8edf2" '
                 f'font-family="sans-serif" font-size="14">START · Lake Akina</text>')
    parts.append(f'<circle cx="{px(e["x"]):.1f}" cy="{py(e["z"]):.1f}" r="8" fill="#ff7ac2"/>')
    parts.append(f'<text x="{px(e["x"])+12:.1f}" y="{py(e["z"]):.1f}" fill="#e8edf2" '
                 f'font-family="sans-serif" font-size="14">FINISH · base</text>')

    # legend
    ly = 52
    for sid in ["S0", "S1", "S2", "S3", "S4", "S5"]:
        parts.append(f'<rect x="{pad}" y="{ly}" width="16" height="16" fill="{COLORS[sid]}"/>')
        parts.append(f'<text x="{pad+22}" y="{ly+13}" fill="#c7cfd8" font-family="sans-serif" '
                     f'font-size="13">{sid} · {NAMES[sid]}</text>')
        ly += 22
    parts.append(f'<text x="{pad}" y="{ly+6}" fill="#9aa4af" font-family="sans-serif" '
                 f'font-size="12">○ = hairpin with inside drainage gutter</text>')

    parts.append("</svg>")
    out = os.path.join(root, "docs", "akina_plan_preview.svg")
    with open(out, "w", encoding="utf-8") as f:
        f.write("\n".join(parts))
    print(f"Wrote {out}")


if __name__ == "__main__":
    main()
