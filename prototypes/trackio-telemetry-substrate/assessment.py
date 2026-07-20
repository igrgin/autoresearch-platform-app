"""Pure assessment state for the throwaway Trackio prototype."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Literal


GateStatus = Literal["pass", "caution", "fail", "not-run"]


@dataclass(frozen=True)
class GateResult:
    name: str
    status: GateStatus
    evidence: tuple[str, ...]
    implication: str


@dataclass(frozen=True)
class AssessmentState:
    results: dict[str, GateResult] = field(default_factory=dict)

    @property
    def verdict(self) -> str:
        replay = self.results.get("offline replay")
        if replay and replay.status == "fail":
            return (
                "Do not use Trackio as Battleground's required V1 telemetry transport. "
                "A Battleground-owned durable spool is still needed; Trackio can remain "
                "an optional exporter or derived view."
            )
        if any(result.status == "caution" for result in self.results.values()):
            return "Trackio is viable only behind explicit Battleground-owned boundaries."
        if self.results and all(
            result.status == "pass" for result in self.results.values()
        ):
            return "All tested gates pass; a bounded Trackio adapter is viable."
        return "Run the probes before judging the adapter."


def record(state: AssessmentState, result: GateResult) -> AssessmentState:
    updated = dict(state.results)
    updated[result.name] = result
    return replace(state, results=updated)

