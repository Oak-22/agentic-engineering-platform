"""Published list rates, and what they can and cannot tell you about spend.

Every number here is a public list price per million tokens, transcribed by
hand. Nothing in a session transcript records what a call was billed, so a
cost in this component is always a reconstruction: list rate times observed
tokens. It ignores negotiated rates, subscription plans that bundle usage,
promotional credits, and the difference between a request that was retried
and one that was charged once. Read the output as relative weight between
work items, not as an invoice.

Rates are Anthropic first-party API rates as of AS_OF. A model this table
does not name is reported as unpriced rather than estimated at a neighbor's
rate, because a plausible-looking wrong number is harder to catch than a
gap. That is also why no OpenAI rates appear here: Codex sessions record
token counts but never a model identifier, so there is nothing to look up.
"""

from __future__ import annotations

from dataclasses import dataclass

AS_OF = "2026-06-24"

#: Cache reads bill at a fraction of the base input rate, and cache writes at
#: a multiple of it, set by the entry's time-to-live. Both are ratios rather
#: than absolute rates so a model's four prices stay derived from one number.
CACHE_WRITE_5M_MULTIPLIER = 1.25
CACHE_WRITE_1H_MULTIPLIER = 2.0
CACHE_READ_MULTIPLIER = 0.1

TOKENS_PER_MILLION = 1_000_000


@dataclass(frozen=True)
class ModelRate:
    """Dollars per million tokens for one model.

    cache_read_per_mtok is stated outright rather than derived, because the
    Fable tier prices cache reads well below the usual fraction of input and
    a derived value would quietly overcharge it.
    """

    input_per_mtok: float
    output_per_mtok: float
    cache_read_per_mtok: float

    def cache_write_per_mtok(self, *, one_hour: bool) -> float:
        multiplier = (
            CACHE_WRITE_1H_MULTIPLIER if one_hour else CACHE_WRITE_5M_MULTIPLIER
        )
        return self.input_per_mtok * multiplier


RATES: dict[str, ModelRate] = {
    "claude-fable-5-1": ModelRate(10.00, 50.00, 0.25),
    "claude-fable-5": ModelRate(10.00, 50.00, 1.00),
    "claude-opus-5": ModelRate(5.00, 25.00, 0.50),
    "claude-opus-4-8": ModelRate(5.00, 25.00, 0.50),
    "claude-opus-4-7": ModelRate(5.00, 25.00, 0.50),
    "claude-opus-4-6": ModelRate(5.00, 25.00, 0.50),
    "claude-sonnet-5": ModelRate(2.00, 10.00, 0.20),
    "claude-sonnet-4-6": ModelRate(3.00, 15.00, 0.30),
    "claude-haiku-4-5": ModelRate(1.00, 5.00, 0.10),
}

#: Claude Code writes this in place of a model id on messages it composed
#: itself — interrupts, error placeholders, and similar. They carry a usage
#: block, but no inference was billed, so they are priced at zero rather
#: than reported as an unknown model needing a rate.
SYNTHETIC_MODEL = "<synthetic>"


def normalize_model(model: str | None) -> str | None:
    """Strip a trailing date snapshot from a model id.

    Transcripts record both `claude-haiku-4-5` and `claude-haiku-4-5-20251001`
    for one model at one price. Matching the table on the undated id keeps a
    snapshot from being reported as an unknown model."""
    if not model:
        return None
    parts = model.rsplit("-", 1)
    if len(parts) == 2 and len(parts[1]) == 8 and parts[1].isdigit():
        return parts[0]
    return model


def rate_for(model: str | None) -> ModelRate | None:
    """The rate for a model, or None when this table cannot price it."""
    normalized = normalize_model(model)
    if normalized is None or normalized == SYNTHETIC_MODEL:
        return None
    return RATES.get(normalized)


def is_priceable(model: str | None) -> bool:
    """Whether a cost figure for this model means anything.

    Distinguishes the two zero-cost cases the report has to keep apart: a
    synthetic message that genuinely cost nothing, and a model whose rate is
    simply missing. Only the second is a gap worth surfacing."""
    return rate_for(model) is not None


def is_pricing_gap(model: str | None) -> bool:
    """Whether an unpriced call is a genuine gap worth flagging.

    `is_priceable` is false for both the synthetic placeholder and a truly
    unknown model, but only the unknown model is a gap: the synthetic
    message was never billed, so counting it here would misreport a
    zero-cost call as unpriced spend."""
    return not is_priceable(model) and normalize_model(model) != SYNTHETIC_MODEL


def estimate_cost(sample) -> float:
    """List-price cost in dollars for one UsageSample.

    Returns 0.0 for anything this table cannot price; call is_priceable to
    tell that apart from a call that really was free. Takes the sample
    structurally rather than by import so this module stays free of a
    dependency on the control plane's reader."""
    rate = rate_for(sample.model)
    if rate is None:
        return 0.0

    write_1h = min(sample.cache_write_1h_tokens, sample.cache_creation_tokens)
    write_5m = sample.cache_creation_tokens - write_1h

    dollars = (
        sample.input_tokens * rate.input_per_mtok
        + sample.output_tokens * rate.output_per_mtok
        + sample.cache_read_tokens * rate.cache_read_per_mtok
        + write_5m * rate.cache_write_per_mtok(one_hour=False)
        + write_1h * rate.cache_write_per_mtok(one_hour=True)
    )
    return dollars / TOKENS_PER_MILLION
