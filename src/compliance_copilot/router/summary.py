"""Framework summary. HIPAA comes from the determination. Nothing else is assessed.

Not assessed means the tool did not look. That is a different statement from
unresolved, which means the tool looked and could not settle HIPAA.
"""

from __future__ import annotations

from compliance_copilot.models import (
    Framework,
    FrameworkSummaryEntry,
    SummaryCategory,
)
from compliance_copilot.router.determine import CoveredEntityDecision

_NAME = {
    Framework.HIPAA: "HIPAA",
    Framework.HBNR: "HBNR",
    Framework.FTC_5: "FTC Act §5",
    Framework.WA_MHMDA: "the Washington My Health My Data Act",
    Framework.CT: "Connecticut's consumer health data law",
    Framework.NV: "Nevada's consumer health data law",
    Framework.TX_NE: "the Texas and Nebraska consent obligations",
    Framework.SOC_2: "SOC 2",
    Framework.PCI_DSS: "PCI DSS",
}


def not_assessed_reason(framework: Framework) -> str:
    """A plain statement that the tool did not look. No intake path, because it didn't."""

    return f"Not assessed. This prototype did not look at {_NAME[framework]}."


def framework_summary(decision: CoveredEntityDecision) -> tuple[FrameworkSummaryEntry, ...]:
    """One entry per v1 framework. HIPAA's category and paths come from the determination."""

    determination = decision.determination
    hipaa = FrameworkSummaryEntry(
        framework=Framework.HIPAA,
        category=determination.hipaa_category,
        derived_from=determination.derived_from,
        reason=decision.rationale,
    )
    rest = tuple(
        FrameworkSummaryEntry(
            framework=framework,
            category=SummaryCategory.NOT_ASSESSED,
            reason=not_assessed_reason(framework),
        )
        for framework in Framework
        if framework is not Framework.HIPAA
    )
    return (hipaa, *rest)
