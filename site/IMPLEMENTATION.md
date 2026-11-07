# VascuQuest website — research experience

This directory contains the premium single-page GitHub Pages website for VascuQuest. The website and the scientific Python library have separate release surfaces.

## Implementation decision

The seventh design decision allowed an architecture-neutral implementation. After inspecting the actual site, the redesign retains its small static HTML/CSS/JavaScript foundation rather than introducing AstroWind or a frontend runtime. The experience consists of one page and two deterministic mathematical explorers, making a static build the smallest maintainable solution. AstroWind remains a design-system reference rather than a copied dependency.

The repository's existing Pages workflow publishes this directory. All asset paths remain relative to the project URL at \`https://knowdyn.github.io/VascuQuest/\`. No package manager or runtime build is needed.

## Visual direction

- Premium software / scientific laboratory hybrid.
- Light editorial surfaces, dark scientific interfaces, oxide-red vessel accents and muted teal metadata.
- Anatomically inspired vector vessel artwork in the hero.
- Three application frontiers: vascular prognostics research, population-level digital twin research, and in silico endovascular innovation.
- Five-step research workflow, deterministic waveform explorer, seven capability modules, evidence taxonomy and open-source installation.
- Motion honours \`prefers-reduced-motion\`; primary narrative remains available as static HTML.

## Scientific demonstration provenance

Interactive chart A recreates the pressure and area waveforms defined in
\`tests/mechanics/test_mechanics.py\`:

- time: 256 evenly spaced samples over [0, 1) s
- pressure: P(t) = 100 + 20 sin(2πt) mmHg
- luminal area: A(t) = 10⁻⁴[1 + 0.08 sin(2πt)] m² (displayed in mm²)

Interactive chart B recreates the pressure waveform and exact first harmonic amplitude from
\`tests/spectral/test_spectral.py\`:

- P(t) = 10000 + 2000 sin(2πt) Pa
- first harmonic amplitude: 2000 Pa
- other non-DC harmonic amplitudes through n=8: 0 Pa for the defined analytical signal

The explorer identifies these as **analytical reference signals** rather than population records. All figures and units are derived from documented test fixtures. Illustrative anatomy and device vectors are conceptual research artwork.

## Local preview

From the repository root:

\`\`\`sh
python -m http.server 8000 --directory site
\`\`\`

Visit \`http://localhost:8000/\`.

## Validation

\`\`\`sh
node --check site/app.js
python3 tests/site/check_site.py
\`\`\`

The dedicated website-checks workflow runs these commands on relevant pull requests and on main. Deployment is handled by the existing \`.github/workflows/pages.yml\` once merged.

## Design tokens

All colour, spacing, component, desktop and mobile rules are in \`site/styles.css\`. The main page remains \`site/index.html\` and the scientific controls are in \`site/app.js\`. The site uses optional Google-hosted DM Sans and IBM Plex Mono fonts with system fallbacks.

Keep scientific source labels and equations consistent with the test suite whenever examples are revised.
