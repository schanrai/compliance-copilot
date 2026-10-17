"""Shared base model and constrained types for the domain models."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Annotated, Any, Self

from pydantic import AfterValidator, BaseModel, ConfigDict, StringConstraints


def _reject_blank(value: str) -> str:
    if not value.strip():
        raise ValueError("must not be empty or whitespace")
    return value


NonBlankStr = Annotated[str, AfterValidator(_reject_blank)]
"""A string with visible content. Stored as given, never stripped, so clause text stays verbatim."""

Identifier = Annotated[
    str, StringConstraints(pattern=r"^[A-Za-z0-9]+(?:[-._][A-Za-z0-9]+)*$")
]
"""A stable id: letters and digits joined by `-`, `.` or `_`. No spaces."""


class ImmutableModel(BaseModel):
    """Frozen, closed to unknown fields, and constructible only through validation.

    `model_construct` and `model_copy(update=...)` skip validators, so both are
    blocked. Without that, an object the validators would reject could still
    be built, and an append-only record could be rewritten.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    @classmethod
    def model_construct(
        cls, _fields_set: set[str] | None = None, **values: Any
    ) -> Self:
        raise TypeError(
            f"{cls.__name__}.model_construct skips validation and is disabled. "
            "Use the constructor or model_validate."
        )

    def model_copy(
        self, *, update: Mapping[str, Any] | None = None, deep: bool = False
    ) -> Self:
        if update:
            raise TypeError(
                f"{type(self).__name__}.model_copy(update=...) skips validation and "
                "is disabled. Build a new object with the constructor or model_validate."
            )
        return super().model_copy(deep=deep)
