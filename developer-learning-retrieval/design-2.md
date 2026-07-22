# Developer Learning Pipeline: Architecture & Sync Strategy

## 1. System Vision
High-velocity software engineering can cause mental model degradation when tools, frameworks, and syntax are implemented faster than they are retained.

This pipeline periodically ingests developer reasoning (thoughts/notes) alongside downstream execution artifacts (code/terminal logs) to generate daily spaced-repetition quizzes, solidifying core system concepts.

---

## 2. Multi-Surface Context Capture

To maintain a zero-friction developer experience while minimizing CPU, memory, and storage overhead, the ingestion engine uses structured text streams rather than continuous video/OCR capture.


┌──────────────────────────────────────┐      ┌──────────────────────────────────────┐
│           Reasoning Layer            │      │           Execution Layer            │
│  (Intent, Architecture, Hypotheses)  │      │  (Diffs, Commands, Error Traces)     │
└──────────────────┬───────────────────┘      └──────────────────┬───────────────────┘
│                                             │
│    ┌──────────────────────────────────┐     │
└────►  Background Polling & Ingestion ◄─────┘
└─────────────────┬────────────────┘
│
▼
┌──────────────────────────────────┐
│   LLM Quiz Generation Engine    │
└──────────────────────────────────┘


### Ingestion Sources
* **Reasoning (Google Keep / Notes):** Captures high-level mental models, architectural rationale, and system trade-offs before implementation.
* **Git Commits & Diffs:** Captures actual AST changes, refactors, and structural code shifts.
* **Terminal Activity:** Captures raw CLI execution, build outcomes, and error/stack traces.

---

## 3. Google Keep Sync Strategy

### The Ingestion Paradox: API vs. Mechanism
Because Google Keep does not offer an official, public REST API for personal end-user accounts, ingestion requires a hybrid approach using the open-source library `gkeepapi`:

1. **Protocol Mechanism (`gkeepapi`):** Authenticates securely via App Passwords and programmatically pulls note bodies and timestamps directly from Keep.
2. **Execution Schedule (Background Polling):** Because Google Keep lacks webhooks/push notifications, real-time streaming is not possible. A local daemon or `cron` job polls the endpoint on a periodic schedule (e.g., nightly at 9:00 PM) to process the last 24 hours of activity.

### Python Ingestion Daemon (Reference Implementation)

```python
import os
from datetime import datetime, timedelta
import gkeepapi

def fetch_daily_reasoning(email: str, app_password: str) -> str:
    """
    Polls Google Keep for notes created or updated in the last 24 hours.
    Returns a unified context string for the LLM Quiz Generator.
    """
    keep = gkeepapi.Keep()
    keep.login(email, app_password)

    cutoff_time = datetime.now() - timedelta(days=1)

    # Filter notes modified within the 24-hour window
    recent_notes = [
        note for note in keep.all()
        if note.timestamps.updated and note.timestamps.updated > cutoff_time
    ]

    context_blocks = []
    for note in recent_notes:
        title = note.title if note.title else "Untitled Note"
        context_blocks.append(f"### Note: {title}\n{note.text}")

    return "\n\n---\n\n".join(context_blocks)

if __name__ == "__main__":
    EMAIL = os.getenv("KEEP_EMAIL")
    APP_PASSWORD = os.getenv("KEEP_APP_PASSWORD")

    reasoning_context = fetch_daily_reasoning(EMAIL, APP_PASSWORD)
    print(f"Ingested {len(reasoning_context)} characters of reasoning data.")



    4. LLM Quiz Prompt Design
The daily morning quiz focuses on bridging intent vs. outcome rather than low-level syntax trivia.

Sample Generated Question Logic
Context: Note states an assumption that building a tool from source is required for Accessibility API entitlements. Terminal logs show brew install --cask succeeded with automatic entitlement grants.

Generated Question: "In your notes yesterday, you hypothesized that building from source was mandatory to grant Accessibility permissions. Did the pre-compiled binary require manual code signing, or did macOS handle the entitlement transition automatically?"
