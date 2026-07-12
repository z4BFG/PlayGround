#!/usr/bin/env python3
"""Embed data/akina_track_spec.json into web/track_data.js as an ES module.

This lets the three.js scene load the track without a local server (works over
file://). Run after regenerating the spec.
"""
import json
import os

root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
spec = json.load(open(os.path.join(root, "data", "akina_track_spec.json"), encoding="utf-8"))
out = os.path.join(root, "web", "track_data.js")
os.makedirs(os.path.dirname(out), exist_ok=True)
with open(out, "w", encoding="utf-8") as f:
    f.write("// Auto-generated from data/akina_track_spec.json — do not edit by hand.\n")
    f.write("// Regenerate: python3 scripts/generate_akina_spec.py && python3 scripts/embed_track.py\n")
    f.write("export const TRACK = ")
    json.dump(spec, f, ensure_ascii=False, separators=(",", ":"))
    f.write(";\n")
print(f"Wrote {out}")
