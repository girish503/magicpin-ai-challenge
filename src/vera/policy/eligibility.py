from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from vera.decision.trigger_analyzer import TriggerAnalysis, TriggerAnalyzer
from vera.domain.models import ResolvedContext


@dataclass(frozen=True)
class EligibilityResult:
    analysis: TriggerAnalysis

    @property
    def eligible(self) -> bool:
        return self.analysis.actionable


def evaluate_trigger_eligibility(resolved: ResolvedContext, now: datetime) -> EligibilityResult:
    return EligibilityResult(analysis=TriggerAnalyzer().analyze(resolved, now))
