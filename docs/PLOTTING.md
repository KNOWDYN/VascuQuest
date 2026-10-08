# Declarative scientific visualization

`vascuquest.plot` treats a figure as a reproducible composition of scientific-result references:

`FigureSpec → PanelSpec → LayerSpec / InsetSpec`

## Supported layers

- line;
- step;
- scatter;
- histogram;
- heatmap;
- ECDF;
- hexbin.

## Large cohorts

A 1,000- or 10,000-observation cohort remains represented. Scatter layers may be rasterized in SVG/PDF to keep output practical, but observations are not silently dropped. ECDF or hexbin are explicit transformations selected by the researcher and recorded in the figure specification.

## Multiple arteries and signals

A panel may contain arbitrary native VascuQuest result layers, including multiple arteries/signals for one virtual subject. Compound figures may combine several panels and inset axes.

## Legend invariant

All legends are external to the scientific plotting axes. The renderer reserves exterior figure space, places the legend at a controlled pad, and checks the rendered legend bounding box against ordinary axes and inset axes. If collision is detected, spacing is increased within a bounded range or the automatic policy selects the bottom exterior region.

## Reproducibility

`write_spec(...)` serializes the figure composition and references each scientific layer by canonical quantity and provenance reference. Rendered output supports PDF, SVG and PNG.
