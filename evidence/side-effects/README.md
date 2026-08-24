# Side Effects

Observations where a platform component produced a real, load-bearing
behavior outside its declared contract — and something came to depend on
that behavior before anyone named it.

These are worth recording separately from case studies because the failure
mode is specific: an undeclared behavior breaks while the declared
contract is still being honored perfectly, so nothing in review, tests, or
type signatures flags the change that breaks it. Writing the dependency
down is what converts it from accident into either a real contract or a
removable coupling.

Each note should state the mechanism concretely enough to verify from
source, say what depends on the behavior, and record whether the
resolution was to **declare** the behavior (make it a contract) or to
**remove** the dependency.

- [`session-identity-via-instruction-ledger.md`](session-identity-via-instruction-ledger.md)
  The instruction-evidence ledger's filename told the agent which session
  it was running in. Resolved by declaring session identity explicitly.
