"""Fixtures for unit tests. Builders live in `factories.py`."""

from __future__ import annotations

import pytest
from factories import IMPLICATION_ID, cited_fields, make_clauses, make_declarations

from compliance_copilot.models import Requirement, RequirementContext


@pytest.fixture
def context() -> RequirementContext:
    return RequirementContext.build(
        clauses=make_clauses(),
        declarations=make_declarations(),
        implication_ids=[IMPLICATION_ID],
    )


@pytest.fixture
def context_with_cited(context: RequirementContext) -> RequirementContext:
    cited = Requirement.model_validate(cited_fields(), context=context)
    return context.with_requirement(cited)
