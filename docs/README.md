# VascuQuest documentation

The repository root is intentionally limited to package-entry files. Internal architecture, scientific contracts, validation contracts, and build governance live here.

## Current governing documents

- [`BUILD_PLAN.md`](BUILD_PLAN.md) — consolidated current build and validation sequence.
- [`DESIGN_CONTRACT.md`](DESIGN_CONTRACT.md) — product and scientific design constraints.
- [`ARCHITECTURE.md`](ARCHITECTURE.md) — package architecture and responsibility boundaries.
- [`DATA_ENGINEERING.md`](DATA_ENGINEERING.md) — canonical-source, acquisition, integrity, and storage rules.
- [`SCIENTIFIC_MODEL.md`](SCIENTIFIC_MODEL.md) — canonical scientific vocabulary and evidence model.
- [`API_PLUGIN_CONTRACT.md`](API_PLUGIN_CONTRACT.md) — Python/API/plugin extension contract.
- [`CLI_CONTRACT.md`](CLI_CONTRACT.md) — command-line contract.
- [`TEST_VALIDATION_CONTRACT.md`](TEST_VALIDATION_CONTRACT.md) — validation tiers and release evidence requirements.

## Historical planning records

The original pre-amendment build plan and the formal core-first amendment are retained under [`history/`](history/) for traceability. They are historical records, not competing governing plans. Where those historical files conflict, the amendment was authoritative; their resolved current effect is incorporated into [`BUILD_PLAN.md`](BUILD_PLAN.md).
