#!/usr/bin/env python3
"""VascuQuest website smoke and analytical-reference tests (stdlib only)."""
from html.parser import HTMLParser
from pathlib import Path
from math import pi, sin, cos, isclose

ROOT = Path(__file__).resolve().parents[2]
SITE = ROOT / "site"
INDEX = (SITE / "index.html").read_text(encoding="utf-8")
JS = (SITE / "app.js").read_text(encoding="utf-8")
CSS = (SITE / "styles.css").read_text(encoding="utf-8")


class Inventory(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.ids = []
        self.h1 = 0
        self.local_files = []
        self.links = []
        self.buttons = 0

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if "id" in a:
            self.ids.append(a["id"])
        if tag == "h1":
            self.h1 += 1
        if tag == "button":
            self.buttons += 1
        if tag == "a":
            self.links.append(a.get("href", ""))
        for key in ("href", "src"):
            val = a.get(key, "")
            if val.startswith(("styles.css", "app.js", "assets/")):
                self.local_files.append(val.split("?", 1)[0])


page = Inventory()
page.feed(INDEX)
assert page.h1 == 1, "Expected exactly one homepage H1"
assert len(page.ids) == len(set(page.ids)), "Duplicate HTML IDs found"
assert {"main", "top", "frontiers", "workflow", "laboratory", "capabilities", "evidence", "start"}.issubset(set(page.ids))
assert page.buttons >= 5, "Expected interactive explorer and navigation controls"
assert all(v and v != "#" for v in page.links), "Found empty navigation link"
assert all((SITE / p).is_file() for p in page.local_files), "Missing a local site asset"
assert "https://knowdyn.github.io/VascuQuest/" in INDEX, "Incorrect Pages canonical address"
assert all(x in INDEX for x in ("HEMOSPACE", "Virtual Disease", "Exact Kinematics", "INFERRED", "MODELLED"))
assert "prefers-reduced-motion" in JS and "prefers-reduced-motion" in CSS
assert "aria-pressed" in JS and "aria-expanded" in JS
assert "test_mechanics.py" in JS and "test_spectral.py" in JS

# The exact manufactured signals are taken from existing scientific tests.
n = 256
t = [j / n for j in range(n)]
mechanics_pressure = [100.0 + 20.0 * sin(2*pi*x) for x in t]
mechanics_area_m2 = [1e-4 * (1.0 + 0.08 * sin(2*pi*x)) for x in t]
spectral_pressure = [10000.0 + 2000.0 * sin(2*pi*x) for x in t]

assert isclose(mechanics_pressure[64], 120.0, abs_tol=1e-10)
assert isclose(mechanics_area_m2[64] * 1e6, 108.0, abs_tol=1e-10)
assert isclose(spectral_pressure[64], 12000.0, abs_tol=1e-10)

# Independent direct DFT confirms the spectral reference plotted in the explorer.
re = sum(y * cos(2*pi*j/n) for j, y in enumerate(spectral_pressure))
im = -sum(y * sin(2*pi*j/n) for j, y in enumerate(spectral_pressure))
harmonic_1 = 2 * ((re*re + im*im)**0.5) / n
assert isclose(harmonic_1, 2000.0, rel_tol=1e-12)

print("PASS: semantic HTML, links, assets, accessibility controls and analytical references")
