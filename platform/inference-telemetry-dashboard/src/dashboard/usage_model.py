"""Aggregate usage samples into the rollups the report renders.

Pure transformation: takes samples in, returns rollups out, touches no
filesystem and no clock. Every I/O decision — which sessions to read, where
the output goes — belongs to the caller, so the aggregation can be tested
against a handful of literal samples.

The organizing question is the one ADR-0003 leaves this component: what did
a governed engineering outcome cost. A work item is therefore the primary
grouping, and the report's honesty depends on the unattributed bucket being
as visible as the attributed ones.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import re

from . import pricing

#: A delivery branch carries its work item key as the segment after the
#: change type — `feature/AEPI-105-govern-delivery-initiation`. The key shape
#: is the one the platform already governs in
#: contracts/agent-run-attempt.schema.json, so a key parsed here is a key
#: that schema would accept.
_WORK_ITEM_PATTERN = re.compile(r"\b([A-Z][A-Z0-9_]*-[1-9][0-9]*)\b")

#: Work sits on a long-lived branch that names no work item — the workbench,
#: an integration branch, a detached read. It is real spend and it is the
#: majority of it, so it is reported as its own bucket rather than dropped.
UNATTRIBUTED = "unattributed"


def work_item_key(branch: str | None) -> str:
    """The work item a branch delivers, or UNATTRIBUTED.

    Reads the first key-shaped segment anywhere in the branch name, so the
    change-type prefix and the trailing slug do not have to be enumerated."""
    if not branch:
        return UNATTRIBUTED
    match = _WORK_ITEM_PATTERN.search(branch)
    return match.group(1) if match else UNATTRIBUTED


@dataclass
class Rollup:
    """Totals for one group of samples.

    Mutable and accumulated in place: a rollup is built by walking samples
    once, and nothing outside this module holds a reference mid-build.
    """

    key: str
    calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    cache_write_tokens: int = 0
    cache_read_tokens: int = 0
    thinking_tokens: int = 0
    estimated_cost: float = 0.0
    unpriced_calls: int = 0
    runtimes: set[str] = field(default_factory=set)
    sessions: set[str] = field(default_factory=set)
    models: set[str] = field(default_factory=set)
    branches: set[str] = field(default_factory=set)
    first_seen: str | None = None
    last_seen: str | None = None

    def add(self, sample) -> None:
        self.calls += 1
        self.input_tokens += sample.input_tokens
        self.output_tokens += sample.output_tokens
        self.cache_write_tokens += sample.cache_creation_tokens
        self.cache_read_tokens += sample.cache_read_tokens
        self.thinking_tokens += sample.thinking_tokens
        self.estimated_cost += pricing.estimate_cost(sample)
        if not pricing.is_priceable(sample.model):
            self.unpriced_calls += 1
        self.runtimes.add(sample.runtime)
        self.sessions.add(f"{sample.runtime}:{sample.session_id}")
        if sample.model:
            self.models.add(sample.model)
        if sample.git_branch:
            self.branches.add(sample.git_branch)
        if sample.timestamp:
            if self.first_seen is None or sample.timestamp < self.first_seen:
                self.first_seen = sample.timestamp
            if self.last_seen is None or sample.timestamp > self.last_seen:
                self.last_seen = sample.timestamp

    @property
    def total_input_tokens(self) -> int:
        """Everything billed as input, at whatever rate."""
        return self.input_tokens + self.cache_write_tokens + self.cache_read_tokens

    @property
    def total_tokens(self) -> int:
        return self.total_input_tokens + self.output_tokens

    @property
    def cache_read_ratio(self) -> float:
        """Share of input tokens served from cache.

        The headline efficiency number: cache reads bill at a tenth of the
        base input rate, so a low ratio on a large volume is where money
        goes. Zero input is reported as zero rather than undefined."""
        denominator = self.total_input_tokens
        return self.cache_read_tokens / denominator if denominator else 0.0

    @property
    def priced_fraction(self) -> float:
        """Share of calls this component could actually price."""
        return (self.calls - self.unpriced_calls) / self.calls if self.calls else 0.0


@dataclass(frozen=True)
class Report:
    """Every rollup the renderer needs, plus the totals it summarizes."""

    total: Rollup
    by_work_item: list[Rollup]
    by_runtime: list[Rollup]
    by_model: list[Rollup]
    by_day: list[Rollup]
    session_count: int
    unpriced_models: list[str]


def _rollup_into(groups: dict[str, Rollup], key: str, sample) -> None:
    groups.setdefault(key, Rollup(key=key)).add(sample)


def _by_cost(groups: dict[str, Rollup]) -> list[Rollup]:
    return sorted(groups.values(), key=lambda r: (-r.estimated_cost, -r.total_tokens))


def build_report(samples) -> Report:
    """Fold samples into every grouping the report shows, in one pass."""
    total = Rollup(key="all")
    work_items: dict[str, Rollup] = {}
    runtimes: dict[str, Rollup] = {}
    models: dict[str, Rollup] = {}
    days: dict[str, Rollup] = {}
    unpriced: set[str] = set()

    for sample in samples:
        total.add(sample)
        _rollup_into(work_items, work_item_key(sample.git_branch), sample)
        _rollup_into(runtimes, sample.runtime, sample)
        _rollup_into(models, sample.model or f"{sample.runtime} (model not recorded)", sample)
        if sample.timestamp:
            _rollup_into(days, sample.timestamp[:10], sample)
        if not pricing.is_priceable(sample.model):
            unpriced.add(sample.model or f"{sample.runtime} (model not recorded)")

    return Report(
        total=total,
        by_work_item=_by_cost(work_items),
        by_runtime=_by_cost(runtimes),
        by_model=_by_cost(models),
        by_day=sorted(days.values(), key=lambda r: r.key),
        session_count=len(total.sessions),
        unpriced_models=sorted(unpriced),
    )
