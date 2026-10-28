"""Model-specific reasoning capabilities for the pinned Copilot SDK."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, TypeGuard

if TYPE_CHECKING:
    from collections.abc import Sequence

    from copilot import ModelInfo
    from copilot.session import ReasoningEffort

# Only levels accepted by the pinned Python SDK's ReasoningEffort API.
SDK_REASONING_EFFORTS: tuple[ReasoningEffort, ...] = (
    "low",
    "medium",
    "high",
    "xhigh",
    "max",
)


def is_reasoning_effort(value: str) -> TypeGuard[ReasoningEffort]:
    """Narrow an explicitly configured level to the SDK's supported type."""
    return value in SDK_REASONING_EFFORTS


@dataclass(frozen=True)
class ReasoningCapabilities:
    """Advertised capabilities, without inventing a default or level list."""

    known: bool = False
    supported_efforts: tuple[ReasoningEffort, ...] = ()
    default_effort: str | None = None


def get_reasoning_capabilities(
    models: Sequence[ModelInfo], model_id: str
) -> ReasoningCapabilities:
    """Read model-specific effort levels; unknown models remain unknown."""
    model = next((model for model in models if model.id == model_id), None)
    if model is None:
        return ReasoningCapabilities()
    supports_reasoning = model.capabilities.supports.reasoning_effort
    advertised = model.supported_reasoning_efforts
    return ReasoningCapabilities(
        known=not supports_reasoning or advertised is not None,
        supported_efforts=tuple(
            effort
            for effort in SDK_REASONING_EFFORTS
            if supports_reasoning and advertised is not None and effort in advertised
        ),
        default_effort=model.default_reasoning_effort,
    )
