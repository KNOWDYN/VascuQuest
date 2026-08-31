"""Public Virtual Disease command group.

The CLI only parses requests, performs source-acquisition safety planning, and
calls the public Virtual Disease Python API. Disease equations remain in the
scientific implementation modules.
"""

from __future__ import annotations

from dataclasses import asdict
from pathlib import Path

import typer

from vascuquest.data import ArtifactState
from vascuquest.disease import (
    DiseaseCondition,
    generate_population,
    preset,
    presets,
    specification,
    write_runtime_bundle,
)
from vascuquest.disease.catalogue import resolve_condition
from vascuquest.errors import AdmissibilityError, DatasetUnavailableError

from .commands import (
    CANONICAL_DATASET,
    _confirm_destructive_or_large,
    _data_context,
    _emit,
    _first_local_probe,
    _identity_dict,
    _parse_assignments,
    _requires_confirmation,
    _resolve_artifact,
    _size_summary,
)


disease_app = typer.Typer(
    help="Generate modelled counterfactual cardiovascular disease populations.",
    no_args_is_help=True,
)

_REQUIRED_ARTIFACT_IDS = (
    "model_configurations",
    "geometry",
    "common_site_waveforms_csv",
)
_QUALIFICATION_STATE = "METRICS_ONLY_THRESHOLDS_NOT_FROZEN"


def _parameter_row(item: object) -> dict[str, object]:
    return {
        "name": getattr(item, "name"),
        "kind": getattr(getattr(item, "kind"), "value"),
        "description": getattr(item, "description"),
        "required": getattr(item, "required"),
        "allowed_values": list(getattr(item, "allowed_values")),
        "minimum": getattr(item, "minimum"),
        "maximum": getattr(item, "maximum"),
        "unit": getattr(item, "unit"),
        "default": getattr(item, "default") if getattr(item, "has_default") else None,
        "has_default": getattr(item, "has_default"),
    }


def _preset_row(descriptor: object) -> dict[str, object]:
    return {
        "condition": getattr(getattr(descriptor, "condition"), "value"),
        "name": getattr(descriptor, "name"),
        "summary": getattr(descriptor, "summary"),
        "parameters": [_parameter_row(item) for item in getattr(descriptor, "parameter_specs")],
        "assumptions": list(getattr(descriptor, "assumptions")),
        "validated_domain": getattr(descriptor, "validated_domain"),
        "citations": list(getattr(descriptor, "citations")),
        "evidence": "MODELLED",
        "clinical_validation": False,
    }


def _resolve_cli_condition(value: str) -> DiseaseCondition:
    try:
        return resolve_condition(value)
    except AdmissibilityError as exc:
        raise typer.BadParameter(str(exc), param_hint="condition") from exc


def _validate_request_before_acquisition(
    *,
    condition: DiseaseCondition,
    patients: int,
    age_group: int,
    parameters: dict[str, object],
) -> None:
    if isinstance(patients, bool) or patients < 1:
        raise typer.BadParameter("--patients must be a positive integer")
    if isinstance(age_group, bool) or age_group < 0:
        raise typer.BadParameter("--age must be a non-negative integer year value")
    try:
        specification(condition, parameters)
    except AdmissibilityError as exc:
        raise typer.BadParameter(str(exc), param_hint="--param") from exc

    if condition is DiseaseCondition.CAROTID_STENOSIS:
        severity = float(parameters["nascet_stenosis"])
        if severity >= 1.0:
            raise typer.BadParameter(
                "carotid_stenosis requires nascet_stenosis < 1 in the executable open-vessel model",
                param_hint="--param",
            )
    if condition is DiseaseCondition.ILIAC_STENOSIS:
        severity = float(parameters["diameter_stenosis"])
        if severity >= 1.0:
            raise typer.BadParameter(
                "iliac_stenosis requires diameter_stenosis < 1 in the executable open-vessel model",
                param_hint="--param",
            )


def _preflight_sources(
    *,
    source: str | None,
    offline: bool,
    yes: bool,
) -> None:
    paths, registry, manifest = _data_context()
    if source is not None:
        source_path = Path(source).expanduser()
        if not source_path.exists() or not source_path.is_dir():
            raise DatasetUnavailableError(
                f"source must identify an existing local PWDB directory: {source_path}"
            )
        try:
            registry.register_local(source_path)
        except ValueError as exc:
            raise DatasetUnavailableError(str(exc)) from exc

    required = tuple(_resolve_artifact(item, manifest) for item in _REQUIRED_ARTIFACT_IDS)
    missing: list[object] = []
    for artifact in required:
        _, inspection = _first_local_probe(artifact, paths, registry)
        if inspection.state is ArtifactState.MISSING:
            missing.append(artifact)

    if not missing:
        return
    if offline:
        names = ", ".join(getattr(item, "artifact_id") for item in missing)
        raise DatasetUnavailableError(
            "Virtual Disease generation requires locally available canonical artifacts "
            f"in --offline mode: {names}"
        )

    planned = tuple(missing)
    typer.echo(
        "Virtual Disease acquisition plan: "
        + ", ".join(
            f"{getattr(item, 'artifact_id')} ({getattr(item, 'filename')})"
            for item in planned
        )
        + f"; expected total size: {_size_summary(planned)}; managed source cache: {paths.source}",
        err=True,
    )
    if _requires_confirmation(planned):
        _confirm_destructive_or_large(
            "Virtual Disease requires large or size-unknown canonical source acquisition",
            yes=yes,
        )


def _generation_summary(runtime: object, bundle_path: Path | None) -> dict[str, object]:
    request = getattr(getattr(runtime, "run_identity"), "request")
    spec = getattr(request, "specification")
    subjects = list(getattr(getattr(runtime, "cohort"), "canonical_subject_ids"))
    statuses = {
        name: status.value for name, status in getattr(runtime, "quantity_statuses")()
    }
    diagnostics = []
    result_counts: dict[str, int] = {}
    for subject_id in subjects:
        state = getattr(runtime, "state")(subject_id)
        result_counts[subject_id] = len(getattr(state, "results"))
        diagnostics.append(
            {
                "subject_id": subject_id,
                **asdict(getattr(getattr(state, "solution"), "diagnostics")),
            }
        )
    return {
        "dataset_identity": _identity_dict(getattr(runtime, "identity")),
        "parent_dataset_identity": _identity_dict(getattr(runtime, "parent_identity")),
        "run_id": getattr(runtime, "run_id"),
        "condition": getattr(getattr(spec, "condition"), "value"),
        "parameters": dict(getattr(spec, "parameters")),
        "preset_version": getattr(spec, "preset_version"),
        "patients": getattr(request, "patients"),
        "age_group": getattr(request, "age_group"),
        "seed": getattr(request, "seed"),
        "canonical_subject_ids": subjects,
        "quantity_statuses": statuses,
        "materialized_quantities": [
            item.canonical_name for item in getattr(runtime, "quantities")()
        ],
        "measurement_sites": [
            item.canonical_site_id for item in getattr(runtime, "locations")()
        ],
        "result_counts_by_subject": result_counts,
        "solver_diagnostics": diagnostics,
        "unsupported_quantities": sorted(
            name for name, status in statuses.items() if status == "NOT_SUPPORTED"
        ),
        "evidence": "MODELLED",
        "healthy_reconstruction_gate": _QUALIFICATION_STATE,
        "clinical_validation": False,
        "storage": (
            "explicit_portable_bundle"
            if bundle_path is not None
            else "runtime_only_process_memory"
        ),
        "bundle_path": None if bundle_path is None else str(bundle_path),
        "warnings": [
            "Virtual Disease output is MODELLED and is not a clinical observation.",
            "Healthy PWDB reconstruction thresholds remain unfrozen; disease output is not clinically validated.",
        ],
    }


@disease_app.command("presets")
def disease_presets(
    output_format: str = typer.Option("text", "--format"),
    output: str | None = typer.Option(None, "--output"),
) -> None:
    """List the four frozen executable Virtual Disease v1 presets."""

    _emit([_preset_row(item) for item in presets()], output_format, output)


@disease_app.command("describe")
def disease_describe(
    condition: str = typer.Argument(...),
    output_format: str = typer.Option("text", "--format"),
    output: str | None = typer.Option(None, "--output"),
) -> None:
    """Describe one disease preset, parameters, assumptions and scope."""

    resolved = _resolve_cli_condition(condition)
    _emit(_preset_row(preset(resolved)), output_format, output)


@disease_app.command("generate")
def disease_generate(
    condition: str = typer.Argument(...),
    patients: int = typer.Option(..., "--patients"),
    age_group: int = typer.Option(..., "--age"),
    param: list[str] = typer.Option([], "--param"),
    seed: int = typer.Option(0, "--seed"),
    dataset: str = typer.Option(CANONICAL_DATASET, "--dataset"),
    source: str | None = typer.Option(None, "--source"),
    offline: bool = typer.Option(False, "--offline"),
    yes: bool = typer.Option(False, "--yes"),
    bundle: str | None = typer.Option(
        None,
        "--bundle",
        help="Explicitly save a portable runtime bundle to this directory.",
    ),
    overwrite: bool = typer.Option(
        False,
        "--overwrite",
        help="Allow an explicitly requested --bundle directory to be replaced.",
    ),
    output_format: str = typer.Option("text", "--format"),
    output: str | None = typer.Option(None, "--output"),
) -> None:
    """Generate a deterministic modelled disease population from healthy PWDB subjects."""

    if overwrite and bundle is None:
        raise typer.BadParameter("--overwrite requires --bundle")
    resolved = _resolve_cli_condition(condition)
    parameters = _parse_assignments(param, "--param")
    _validate_request_before_acquisition(
        condition=resolved,
        patients=patients,
        age_group=age_group,
        parameters=parameters,
    )
    _preflight_sources(source=source, offline=offline, yes=yes)

    typer.echo(
        "Virtual Disease scientific boundary: MODELLED counterfactual data; "
        f"healthy reconstruction gate={_QUALIFICATION_STATE}; not clinically validated.",
        err=True,
    )
    runtime = generate_population(
        patients=patients,
        age_group=age_group,
        condition=resolved,
        parameters=parameters,
        seed=seed,
        dataset=dataset,
        source=source,
        offline=offline,
    )
    bundle_path = None
    if bundle is not None:
        bundle_path = write_runtime_bundle(
            runtime,
            Path(bundle).expanduser(),
            overwrite=overwrite,
        )
    _emit(_generation_summary(runtime, bundle_path), output_format, output)


__all__ = ["disease_app"]
