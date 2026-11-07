/* Minimal, dependency-free website interactions.
 * The explorer recreates deterministic manufactured input signals from:
 * tests/mechanics/test_mechanics.py and tests/spectral/test_spectral.py
 * These are analytical qualification fixtures, labelled as such in the UI.
 */
(() => {
  "use strict";
  const doc = document;
  const root = doc.documentElement;
  const header = doc.querySelector("[data-header]");
  const menuButton = doc.querySelector("[data-menu-toggle]");
  const mobileNav = doc.querySelector("[data-mobile-nav]");
  const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  function syncHeader() {
    header?.classList.toggle("scrolled", window.scrollY > 12);
  }
  syncHeader();
  window.addEventListener("scroll", syncHeader, { passive: true });

  function closeMenu() {
    if (!menuButton || !mobileNav) return;
    menuButton.setAttribute("aria-expanded", "false");
    menuButton.setAttribute("aria-label", "Open navigation");
    mobileNav.hidden = true;
  }
  if (menuButton && mobileNav) {
    menuButton.addEventListener("click", () => {
      const expanding = menuButton.getAttribute("aria-expanded") !== "true";
      menuButton.setAttribute("aria-expanded", String(expanding));
      menuButton.setAttribute("aria-label", expanding ? "Close navigation" : "Open navigation");
      mobileNav.hidden = !expanding;
    });
    mobileNav.querySelectorAll("a").forEach(a => a.addEventListener("click", closeMenu));
    window.addEventListener("keydown", e => { if (e.key === "Escape") closeMenu(); });
    window.addEventListener("resize", () => { if (window.innerWidth > 1000) closeMenu(); });
  }

  const reveal = [...doc.querySelectorAll(".reveal")];
  if (!reducedMotion && "IntersectionObserver" in window) {
    root.classList.add("enhanced");
    const observer = new IntersectionObserver((entries, obs) => {
      for (const entry of entries) {
        if (entry.isIntersecting) {
          entry.target.classList.add("revealed");
          obs.unobserve(entry.target);
        }
      }
    }, { threshold: 0.04, rootMargin: "0px 0px -20px 0px" });
    reveal.forEach(el => observer.observe(el));
  } else {
    reveal.forEach(el => el.classList.add("revealed"));
  }

  const copyButton = doc.querySelector("[data-copy]");
  if (copyButton) {
    copyButton.addEventListener("click", async () => {
      if (!navigator.clipboard?.writeText) return;
      try {
        await navigator.clipboard.writeText(copyButton.getAttribute("data-copy"));
        copyButton.textContent = "COPIED";
        copyButton.setAttribute("aria-label", "Installation command copied");
      } catch {
        copyButton.textContent = "SELECT TEXT";
        copyButton.setAttribute("aria-label", "Select installation command manually");
      }
    });
  }

  const SVG_NS = "http://www.w3.org/2000/svg";
  const chart = doc.getElementById("lab-chart");
  if (!chart) return;

  const chartLine = doc.getElementById("chart-line-path");
  const chartArea = doc.getElementById("chart-area-path");
  const yLabels = doc.getElementById("chart-y-labels");
  const xLabels = chart.querySelector(".chart-ticks");
  const controls = doc.querySelector(".quantity-switch");
  const modes = [...doc.querySelectorAll("[data-mode]")];
  const sourceAnchor = doc.getElementById("chart-source");
  let mode = "mechanics";
  let quantity = "pressure";

  /* Signal values are exact functions given by the checked-in scientific tests.
     Mechanics: 100+20*sin(2*pi*t) mmHg; 1e-4*(1+.08*sin) m².
     Spectral: 10000+2000*sin(2*pi*t) Pa, first harmonic amplitude 2000 Pa. */
  const mechanicsBase = "https://github.com/KNOWDYN/VascuQuest/blob/main/tests/mechanics/test_mechanics.py";
  const spectralBase = "https://github.com/KNOWDYN/VascuQuest/blob/main/tests/spectral/test_spectral.py";

  const configs = {
    "mechanics:pressure": {
      title: "Arterial pressure waveform",
      category: "PRESSURE–AREA MECHANICS",
      source: "Manufactured mechanics test",
      file: mechanicsBase,
      equation: "P(t) = 100 + 20 sin(2πt) mmHg",
      mean: "100.0", amp: "20.0", unit: "mmHg",
      yMin: 75, yMax: 125,
      sample: t => 100 + 20 * Math.sin(2 * Math.PI * t),
      yUnit: "mmHg", spectrum: false
    },
    "mechanics:area": {
      title: "Cross-sectional area waveform",
      category: "PRESSURE–AREA MECHANICS",
      source: "Manufactured mechanics test",
      file: mechanicsBase,
      equation: "A(t) = 10⁻⁴[1 + 0.08 sin(2πt)] m²",
      mean: "100.0", amp: "8.0", unit: "mm²",
      yMin: 88, yMax: 112,
      sample: t => 100 * (1 + .08 * Math.sin(2 * Math.PI * t)),
      yUnit: "mm²", spectrum: false
    },
    "spectral:waveform": {
      title: "Analytical pressure signal",
      category: "SPECTRAL REFERENCE",
      source: "Manufactured spectral test",
      file: spectralBase,
      equation: "P(t) = 10000 + 2000 sin(2πt) Pa",
      mean: "10,000", amp: "2,000", unit: "Pa",
      yMin: 7000, yMax: 13000,
      sample: t => 10000 + 2000 * Math.sin(2 * Math.PI * t),
      yUnit: "Pa", spectrum: false
    },
    "spectral:spectrum": {
      title: "Pressure harmonic amplitudes",
      category: "SPECTRAL REFERENCE",
      source: "Manufactured spectral test",
      file: spectralBase,
      equation: "A₁ = 2000 Pa; Aₙ = 0 for n = 2,…,8",
      mean: "n = 1", amp: "2,000", unit: "Pa",
      yMin: 0, yMax: 2400,
      sample: n => n === 1 ? 2000 : 0,
      yUnit: "Pa", spectrum: true
    }
  };

  function svgText(x, y, value, anchor = "end") {
    const el = doc.createElementNS(SVG_NS, "text");
    el.setAttribute("x", String(x));
    el.setAttribute("y", String(y));
    el.setAttribute("text-anchor", anchor);
    el.textContent = value;
    return el;
  }
  function yPos(v, cfg) {
    return 275 - ((v - cfg.yMin) / (cfg.yMax - cfg.yMin)) * 240;
  }
  function render() {
    const cfg = configs[mode + ":" + quantity];
    if (!cfg) return;
    doc.getElementById("chart-title").textContent = cfg.title;
    doc.getElementById("chart-category").textContent = cfg.category;
    doc.getElementById("signal-source").textContent = cfg.source;
    doc.getElementById("chart-mean").innerHTML = cfg.mean + ' <small>' + (cfg.spectrum ? "peak" : cfg.unit) + "</small>";
    doc.getElementById("chart-amplitude").innerHTML = cfg.amp + " <small>" + cfg.unit + "</small>";
    doc.getElementById("chart-equation").textContent = cfg.equation;
    sourceAnchor.href = cfg.file;
    chart.setAttribute("aria-label", cfg.title + ". Analytical reference: " + cfg.equation);

    yLabels.replaceChildren();
    xLabels.replaceChildren();
    for (let j = 0; j < 5; j++) {
      const val = cfg.yMax - j * (cfg.yMax - cfg.yMin) / 4;
      const fmt = (Math.abs(val) >= 1000) ? val.toLocaleString("en-GB",{maximumFractionDigits:0}) : String(Math.round(val * 10) / 10);
      yLabels.appendChild(svgText(43, 39 + j * 60, fmt));
    }
    const xTicks = cfg.spectrum
      ? ["0","2","4","6","8"]
      : ["0.00","0.25","0.50","0.75","1.00 s"];
    xTicks.forEach((label,i) => xLabels.appendChild(svgText(55 + i * 699 / 4,303,label,i===4?"end":i===0?"start":"middle")));

    let path = "";
    let fillPath = "";
    if (cfg.spectrum) {
      const barWidth = 22;
      const bars = [];
      for (let n = 0; n <= 8; n++) {
        const x = 55 + (n / 8) * 699;
        const y = yPos(cfg.sample(n),cfg);
        const top = Math.min(275,y);
        const ht = Math.max(1,275-top);
        bars.push("M " + (x-barWidth/2) + " 275 V " + top + " h " + barWidth + " V 275 Z");
      }
      fillPath = bars.join(" ");
      chartLine.setAttribute("d", "");
      chartArea.setAttribute("d", fillPath);
      chartArea.style.fillOpacity = ".85";
      chartArea.style.fill = "#d28d8f";
    } else {
      const pts = [];
      for (let n = 0; n < 256; n++) {
        const t = n/256;
        pts.push([55+t*699,yPos(cfg.sample(t),cfg)]);
      }
      path = pts.map((p,i) => (i?"L":"M") + p[0].toFixed(2) + " " + p[1].toFixed(2)).join(" ");
      fillPath = path + " L " + pts[pts.length-1][0].toFixed(2) + " 275 L 55 275 Z";
      chartLine.setAttribute("d",path);
      chartArea.setAttribute("d",fillPath);
      chartArea.style.fillOpacity = ".07";
      chartArea.style.fill = "#d28d8f";
    }
  }

  function updateControls() {
    modes.forEach(button => {
      const selected = button.dataset.mode === mode;
      button.classList.toggle("active", selected);
      button.setAttribute("aria-pressed", String(selected));
    });
    const quantities = mode === "mechanics"
      ? [["pressure","Pressure"],["area","Area"]]
      : [["waveform","Waveform"],["spectrum","Spectrum"]];
    controls.replaceChildren();
    for (const [id,label] of quantities) {
      const button = doc.createElement("button");
      button.type = "button";
      button.className = "quantity-button" + (id === quantity ? " active" : "");
      button.setAttribute("data-quantity",id);
      button.setAttribute("aria-pressed",String(id===quantity));
      button.textContent = label;
      controls.appendChild(button);
    }
    render();
  }
  modes.forEach(button => button.addEventListener("click", () => {
    mode = button.dataset.mode;
    quantity = mode === "mechanics" ? "pressure" : "waveform";
    updateControls();
  }));
  controls.addEventListener("click", event => {
    const button = event.target.closest("[data-quantity]");
    if (!button) return;
    quantity = button.dataset.quantity;
    updateControls();
  });

  updateControls();
})();
