# Scientific plotting in VascuQuest 1.0

## 1. Purpose

`vascuquest.plot` is a declarative scientific-figure engine for VascuQuest results. It is designed for publication-grade in-silico research figures, including multi-panel layouts, multiple arterial waveforms, large cohorts, spectra, mechanics results, heatmaps, distributions, and insets.

It is not a thin Matplotlib wrapper and it is not the authoritative source of scientific values. Figures are representations of already-defined VascuQuest scientific results and explicitly declared visual transformations.

## 2. Core figure model

The v1 figure architecture is:

```text
FigureSpec
├── PanelSpec
│   ├── LayerSpec
│   ├── LayerSpec
│   └── InsetSpec
├── PanelSpec
└── LegendPolicy
```

### `FigureSpec`

Controls:

- ordered panels;
- number of columns;
- figure width;
- height per row;
- optional figure title;
- legend policy;
- DPI.

Panel IDs must be unique.

### `PanelSpec`

Controls:

- panel ID;
- ordered layers;
- title;
- x/y labels;
- linear/log axes;
- x/y limits;
- zero or more inset specifications.

Every panel must contain at least one layer.

### `InsetSpec`

Defines an inset inside a parent panel using axes-fraction bounds:

```text
(x, y, width, height)
```

Inset bounds must remain entirely within the parent axes. Insets may have their own layers, title, and axis limits.

### `LayerSpec`

A layer references one or two `ScientificResult` objects and declares how they should be rendered.

Supported v1 layer kinds:

```text
line
scatter
step
hist
heatmap
hexbin
ecdf
```

Optional layer properties include label, alpha, marker, linewidth, bin count, and explicit transform.

## 3. Scientific result references

A layer specification stores references to the scientific meaning of the plotted result, including:

- canonical quantity name;
- provenance reference;
- method ID.

The serialized `FigureSpec` therefore records the scientific objects used to construct the figure rather than preserving only appearance parameters.

## 4. X-coordinate behavior

If `LayerSpec.x` is supplied, its values become the x data.

If x is omitted:

- a `Waveform` uses its explicit time coordinate;
- a result with a coordinate matching its first dimension uses that coordinate;
- otherwise a deterministic numeric index is used.

Line/scatter/step/hexbin layers require compatible one-dimensional x/y values. Heatmaps require a two-dimensional y result.

## 5. Multiple arterial time series

One virtual subject may contribute multiple arterial waveforms to one panel:

```python
FigureSpec(
    panels=(
        PanelSpec(
            "A",
            layers=(
                LayerSpec("line", aortic_pressure, label="Aortic root"),
                LayerSpec("line", carotid_pressure, label="Carotid"),
                LayerSpec("line", femoral_pressure, label="Femoral"),
            ),
            xlabel="Time",
            ylabel="Pressure",
        ),
    )
)
```

Each line remains a separate scientific result with its own location/provenance context.

## 6. Large cohorts

The plotting layer has a hard rule:

> Large cohorts must never be silently thinned, sampled, or truncated for visual convenience.

A 1,000-subject scatter plot represents all 1,000 observations unless the researcher explicitly requests a transformation such as ECDF or hexbin.

For large scatter layers, VascuQuest may set Matplotlib rasterization during rendering. Rasterization changes the graphics representation inside vector output; it does **not** remove observations.

For large heatmaps, the image layer may also be rasterized for rendering efficiency.

## 7. Explicit transformations

The v1 plotting engine distinguishes rendering optimization from scientific transformation.

### Rendering optimization

Examples:

- rasterizing a 5,000-point scatter layer;
- rendering a large heatmap as an image.

These do not change the underlying observations.

### Scientific/visual transformation

Examples:

- ECDF;
- hexagonal binning;
- histogram binning;
- any future density estimate;
- mean/CI summaries;
- quantile bands.

These change how raw observations are represented and therefore must be explicit in the layer specification or upstream analysis result.

The current `LayerSpec.transform` contract recognizes:

```text
identity
ecdf
hexbin
```

## 8. ECDF

An ECDF layer sorts all represented y values and plots cumulative empirical probability:

```text
p_i = i / N
```

No observations are discarded.

Use ECDF when cohort distributions are more informative than an overplotted scatter cloud.

## 9. Hexbin

A hexbin layer requires explicit x and y results. It aggregates the spatial density of observations into hexagonal cells.

This is an explicit transformation, not silent simplification. The figure specification records that hexbin was used.

## 10. Histograms

Histogram layers use an explicit bin count. Binning is part of the figure method and should be reported when it materially affects interpretation.

## 11. Heatmaps

Heatmap layers require a two-dimensional `ScientificResult`.

Appropriate examples include:

- time-frequency magnitude matrices;
- path-position × time fields;
- cohort × feature matrices where that representation is scientifically meaningful.

The plotting layer does not invent the semantic meaning of matrix axes; the source result must carry appropriate scientific context.

## 12. Compound figures

Multiple panels are first-class. Example:

```text
Figure
├── Panel A: pressure waveforms at multiple arteries
├── Panel B: pressure-area loop
├── Panel C: impedance harmonics
│   └── inset: first five harmonics
└── Panel D: cohort response scatter
```

`FigureSpec.ncols` controls the panel grid. Unused Matplotlib axes are removed.

## 13. Insets

Insets are child axes of the parent panel and participate in collision checking.

An inset may contain its own layers and may define independent x/y limits.

The v1 renderer recursively includes child inset axes when assessing legend collisions. This is necessary because Matplotlib stores inset axes as child axes rather than ordinary top-level figure axes.

## 14. Legend policy — hard invariant

The v1 legend contract is non-negotiable:

> Legends must remain outside the scientific plotting region and must not collide with axes, tick labels, axis labels, titles, insets, or neighboring panels.

`LegendPolicy` supports:

```text
auto
right
bottom
```

The renderer:

1. gathers legend entries across all panels and inset child axes;
2. de-duplicates identical labels;
3. measures the rendered legend bounding box;
4. chooses right or bottom placement in `auto` mode based on legend geometry/entry count;
5. reserves only the space needed within configured limits;
6. renders the legend outside the plot region;
7. checks the legend bounding box against every axes tight bounding box, including insets;
8. adjusts padding iteratively if collision is detected.

## 15. Legend spacing

The legend must not be arbitrarily far from the plot.

The default policy constrains exterior padding as a fraction of figure size and measures the actual legend dimensions before reserving space. This avoids both:

- legends touching/colliding with axes labels;
- oversized blank margins created by fixed `bbox_to_anchor` guesses.

Relevant `LegendPolicy` controls include:

- minimum/maximum pad fraction;
- maximum right-side figure fraction;
- maximum right-side entry count before preferring bottom placement;
- maximum entries per bottom legend column.

## 16. Figure-spec serialization

`FigureSpec.to_dict()` produces a serializable representation containing:

- schema version;
- layout/dimensions;
- legend policy;
- panels;
- layers;
- result references;
- explicit transformations;
- inset definitions.

`write_spec(spec, destination)` writes the JSON figure specification.

This allows a paper figure to retain a reproducible recipe independent of the rendered image.

## 17. Export formats

`render(spec, destination)` supports:

```text
.pdf
.svg
.png
```

Other destination suffixes fail explicitly.

SVG/PDF are preferred for vector scientific output where practical. Large rasterized layers can coexist inside vector figures without dropping points.

## 18. CLI convenience commands

### Multi-series panel

```text
vascuquest plot series aortic.json carotid.json femoral.json \
  --output figure.svg \
  --title "Arterial pressure waveforms" \
  --spec-output figure-spec.json
```

### Scatter

```text
vascuquest plot scatter baseline.json response.json \
  --output response.svg \
  --title "Baseline phenotype vs modelled response" \
  --spec-output response-spec.json
```

The Python API is the richer surface for multi-panel/inset figures.

## 19. Publication workflow

Recommended pattern:

```text
ScientificResult / Waveform
        ↓
mechanics / spectral / stats (if needed)
        ↓
FigureSpec
        ↓
render to SVG/PDF/PNG
        ↓
write FigureSpec JSON alongside figure
```

The figure should never be the only retained representation of an analysis result.

## 20. Statistical annotations

Statistical annotations should come from explicit `vascuquest.stats` results or other declared analytical results. Plotting code must not secretly recompute p-values, confidence intervals, or summaries merely to decorate a figure.

This keeps analysis and visualization responsibilities separate.

## 21. Multiple scales and units

The current v1 panel model supports one x/y axis scale per panel (`linear` or `log`). Researchers should avoid plotting quantities with incompatible units on the same axis merely because the renderer allows multiple layers.

If dual-axis support is added in a future release, it must be explicit and scientifically constrained.

## 22. Optional dependency

Install plotting support with:

```text
pip install "vascuquest[plot]"
```

Matplotlib is optional and imported only when rendering is requested. Core VascuQuest can be used without plotting dependencies.

## 23. Non-claims

The plotting system does not:

- make modelled results clinically validated;
- determine which visualization is scientifically appropriate without researcher judgment;
- silently select representative subjects;
- downsample cohorts;
- convert density/binning into raw observations;
- treat graphics as authoritative numerical data;
- guarantee acceptance by a specific journal style guide without user formatting choices.

Its purpose is reproducible, collision-safe, publication-grade rendering of scientifically defined VascuQuest results.
