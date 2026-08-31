"""Runtime vector naming rules for Virtual Disease v1."""

from __future__ import annotations

import re

from .catalogue import resolve_condition
from .model import DiseaseCondition


_ALIAS_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_]*$")


def disease_vector_name(source_alias: str, condition: DiseaseCondition | str) -> str:
    """Return the storage identity for one disease-qualified runtime vector.

    The canonical scientific quantity name remains unchanged. This function
    qualifies only the runtime/source vector label.
    """

    if not isinstance(source_alias, str):
        raise TypeError("source_alias must be a string")
    if _ALIAS_RE.fullmatch(source_alias) is None:
        raise ValueError("source_alias must use simple identifier syntax")
    resolved = resolve_condition(condition)
    return f"{source_alias}__vd_{resolved.value}"


__all__ = ["disease_vector_name"]
