# VascuQuest public research experience

The website is a dependency-free HTML/CSS/JavaScript GitHub Pages project. The browser reads a compact research summary generated entirely from the supplied \`Cardioacoustics_ECs_v1.0.0.zip\` archive.

## Interactive Research Signal Explorer

This version presents an integrated computational cardiovascular laboratory containing:

- Five mapped arterial sites from the archived PWDB study: proximal aorta (segment 1), left common carotid (15), abdominal aorta IV (39), left common iliac (42) and left femoral path (46).
- Three archived arterial wall states: healthy, partially stiffened and stiffened.
- Three frequency-response channels: pressure transfer gain (dB), tangential endothelial traction transfer (mPa per Pa root pressure) and wall-displacement transfer (nm per Pa root pressure).
- Cohort medians over 102 virtual subjects. The archive contains 61 source frequency bins from 10–40 Hz; the public plot displays an every-third-bin subset (21 sampled frequencies).
- WP2/A2 exposure at 18 Hz and an independently literature-anchored 310 Pa root pressure. The inspector presents cohort medians of absolute local pressure, local traction, wall displacement, wall acceleration and traction gradient.
- An eighteen-hertz harmonic trace reconstructed mathematically from the complex local WP2/A2 pressure phasors for archived virtual subject #1048. This is explicitly presented as a single-frequency phasor reconstruction, rather than a measured waveform.
- Six-stratum (ages 25–75) median carotid–femoral PWV comparisons for the three model states.
- A cross-artery matrix of median local pressure phasor magnitudes for WP2/A2.
- A distinct model catalogue linking to VascuQuest's four disease presets: carotid and iliac stenosis, abdominal aortic aneurysm, and large-artery stiffening.

The archived vascular wall states, the wider Virtual Disease model presets and the concept of cardiovascular risk research have separate scientific meanings. The website uses explicit labels and provenance to keep them distinct. All quantitative signals and metrics shown in the explorer are derived from the attached archive; the browser does not manufacture novel physiological records.

## Source and regeneration

Source archive: \`Cardioacoustics_ECs_v1.0.0.zip\`, SHA-256:

\`\`\`
2848af6d21765129ba66179734ee54a756e484c833de2af3c22143c437f693bb
\`\`\`

Archive directories used:

- \`population/transfer_selected.npz\`
- \`physiological_exposure/wp2_primary_exposure.npz\`
- \`inputs/cohort/site_map.csv\`
- \`study_manifest.json\`

Regenerate the curated static JSON with NumPy:

\`\`\`sh
python tools/site/build_cardioacoustics_dashboard.py \
  Cardioacoustics_ECs_v1.0.0.zip site/assets/cardioacoustics-dashboard.json
\`\`\`

The uploaded source ZIP is not redistributed with the website. The curated \`site/assets/cardioacoustics-dashboard.json\` contains numerically derived cohort summaries and one virtual subject's 18 Hz phasor values. The raw archive records remain authoritative.

Original PWDB source DOI: \`10.5281/zenodo.3275625\`. The archive is a separate frozen research package, version 1.0.0.

## Local preview

\`\`\`sh
python -m http.server 8000 --directory site
\`\`\`

Open \`http://localhost:8000/\`.

Run website smoke tests:

\`\`\`sh
node --check site/app.js
python tests/site/check_site.py
\`\`\`

The existing \`.github/workflows/pages.yml\` publishes \`site/\`. The \`site-checks.yml\` workflow validates syntax, scientific summary structure and provenance on relevant pull requests.
