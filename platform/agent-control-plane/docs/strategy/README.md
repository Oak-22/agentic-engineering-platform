# Strategy Notes

Index for domain-agnostic strategy notes: reasoning about platform-level
design choices that isn't tied to one delivery outcome or Jira issue.

- [Retrieval Strategy for Cached Provider Documentation](retrieval-vs-lexical-search.md)
  Why the provider-docs mirror uses lexical `grep`/`sed` search instead of
  embedding-based RAG, and what corpus profile would change that answer.
- [Session Transcripts as a Cross-Agent Pickup Source](session-transcript-cross-agent-pickup.md)
  The read-only reader (`locate_sessions`/`read_turns`) is implemented and
  verified against real local data; no consumer (extraction, promotion,
  cross-agent scanning) is built on top of it yet.
- [Native Provider State as a Port, Not a Dependency](native-provider-state-ports.md)
  Canonical explanation of the ports-and-adapters pattern already present,
  unnamed, in four mechanisms across this repo, and scopes the
  still-missing change-detection piece. Other notes that apply this
  pattern to one mechanism (e.g. the session-transcript note above) link
  back here rather than restating it.
