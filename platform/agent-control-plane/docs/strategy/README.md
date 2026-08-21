# Strategy Notes

Index for domain-agnostic strategy notes: reasoning about platform-level
design choices that isn't tied to one delivery outcome or Jira issue.

- [Retrieval Strategy for Cached Provider Documentation](retrieval-vs-lexical-search.md)
  Why the provider-docs mirror uses lexical `grep`/`sed` search instead of
  embedding-based RAG, and what corpus profile would change that answer.
- [Session Transcript Reader and Its Consumers](session-transcript-reader.md)
  The read-only reader (`locate_sessions`/`read_turns`) is implemented and
  verified against real local data, with one consumer built on it — the
  `capture-session-trail` skill, which renders a session for a human
  reviewer. Runtime-neutral extraction for another *agent* to pick up, and
  cross-agent scanning, are still deferred.
- [One Owner Per Decision, Not One Function Per Similar Code](one-owner-per-decision.md)
  When duplicated-looking implementations should be consolidated and when
  they should not, and the failure it prevents: copies that drift into
  silent disagreement with nothing to report it. Generalizes the argument
  the two notes around it make for their own domains.
- [Native Provider State as a Port, Not a Dependency](native-provider-state-ports.md)
  Canonical explanation of the ports-and-adapters pattern already present,
  unnamed, in four mechanisms across this repo, and scopes the
  still-missing change-detection piece. Other notes that apply this
  pattern to one mechanism (e.g. the session-transcript note above) link
  back here rather than restating it.
