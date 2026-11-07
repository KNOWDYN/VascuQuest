#!/usr/bin/env python3
"""VascuQuest website smoke tests (Python standard library only)."""
from html.parser import HTMLParser
from pathlib import Path
import json
from math import isclose

ROOT = Path(__file__).resolve().parents[2]
SITE = ROOT / "site"
HTML = (SITE / "index.html").read_text(encoding="utf-8")
JS = (SITE / "app.js").read_text(encoding="utf-8")
CSS = (SITE / "styles.css").read_text(encoding="utf-8")
DATA_PATH = SITE / "assets" / "cardioacoustics-dashboard.json"
DATA = json.loads(DATA_PATH.read_text(encoding="utf-8"))


class Inventory(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.ids = []
        self.h1 = 0
        self.files = []
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
        for key in ("href", "src", "data-source"):
            val = a.get(key, "")
            if val.startswith(("styles.css", "app.js", "assets/")):
                self.files.append(val.split("?", 1)[0])


page = Inventory()
page.feed(HTML)
assert page.h1 == 1, "Expected exactly one H1"
assert len(page.ids) == len(set(page.ids)), "Duplicate IDs"
assert {"main", "top", "frontiers", "workflow", "laboratory", "capabilities", "evidence", "start"}.issubset(page.ids)
assert {"rc-spectrum", "rc-phasor", "rc-pwv", "rc-matrix-body", "rc-pressure"}.issubset(page.ids)
assert page.buttons >= 10, "Research controls missing"
assert all(a and a != "#" for a in page.links), "Invalid internal links"
assert all((SITE / file).is_file() for file in page.files), "Local site asset missing"
assert "https://knowdyn.github.io/VascuQuest/" in HTML
assert "The future of endovascular research," in HTML
assert "assets/stroke-intervention.svg" in HTML
assert "prefers-reduced-motion" in JS and "prefers-reduced-motion" in CSS
assert "aria-pressed" in JS and "aria-expanded" in JS
assert "cardioacoustics-dashboard.json" in HTML
assert "1048" in HTML, "Subject provenance missing"
assert "M1" in HTML, "Stroke imaging context missing"

assert DATA["archive"] == "Cardioacoustics_ECs_v1.0.0"
assert DATA["subjects"] == 102
assert len(DATA["sites"]) == 5 and len(DATA["states"]) == 3
assert DATA["states"] == ["healthy", "partial", "stiff"]
assert DATA["sourceFrequencyHz"]["count"] == 61
assert DATA["sourceFrequencyHz"]["start"] == 10 and DATA["sourceFrequencyHz"]["end"] == 40
assert len(DATA["sampleFrequencyHz"]) == 21
assert isclose(DATA["sampleFrequencyHz"][0], 10.0) and isclose(DATA["sampleFrequencyHz"][-1], 40.0)
assert DATA["source_event_frequency_hz"] == 18
assert DATA["source_event_pressure_pa"] == 310
assert len(DATA["sha256"]) == 64

sites = {site["id"]: site for site in DATA["sites"]}
assert set(sites) == {"proximal_aorta", "left_common_carotid", "abdominal_aorta_iv", "left_common_iliac", "left_femoral_path"}
assert [sites[s]["segment"] for s in ["proximal_aorta", "left_common_carotid", "abdominal_aorta_iv", "left_common_iliac", "left_femoral_path"]] == [1, 15, 39, 42, 46]

for site in DATA["sites"]:
    assert len(site["states"]) == 3
    for state in site["states"]:
        for key in ("gain", "traction", "motion"):
            assert len(state[key]) == 21
            assert all(isinstance(v, (int, float)) for v in state[key])
        assert len(state["refP"]) == 2
        assert all(state[k] >= 0 for k in ("p50", "t50", "m50", "acc50", "grad50"))

assert isclose(sites["left_common_carotid"]["states"][0]["p50"], 240.6)
assert isclose(sites["abdominal_aorta_iv"]["states"][0]["p50"], 313.0)
assert isclose(sites["left_common_carotid"]["states"][0]["t50"], 0.420)
assert isclose(sites["left_common_carotid"]["states"][0]["m50"], 8.71)
assert all(len(DATA["pwv"][wall]) == 6 for wall in DATA["states"])
assert isclose(DATA["pwv"]["healthy"][0], 5.95)
assert isclose(DATA["pwv"]["stiff"][-1], 12.44)

print("PASS: semantic page, responsive controls, authentic archive summary, 5 arteries, 3 states and source provenance")
