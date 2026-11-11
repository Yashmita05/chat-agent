# Design

## Goal
A chat agent that answers **fast**, gets facts **right**, and **remembers what
the user asked and when**, using exactly one tool: web search.

## Decisions

### 1. One tool, used sparingly
The only tool is Anthropic's server-side `web_search` (`max_uses: 3`).
Server-side means no client tool loop: one streaming request, no extra round
trips for us to orchestrate. The system prompt tells the model *when not to
search* (stable facts) and *when to* (anything time-sensitive or uncertain),
because the biggest latency cost is an unnecessary search. Typical questions
need zero or one search.

### 2. Speed
- Default model is the small/fast tier (`claude-haiku-5-5`); `AGENT_MODEL`
  swaps in a stronger one for hard questions.
- Responses stream token by token, so first words appear immediately.
- The static instructions sit before a prompt-cache breakpoint; only the date
  and question log (which change every turn) come after it.
- `max_tokens=1024` and a "lead with the answer, be brief" rule bound output.
- Short-term context is capped at 12 turns.

### 3. Correctness
- The current date/time (in the user's timezone) is injected every turn, so
  "latest" and "yesterday" resolve correctly and queries can carry the year.
- Rules: never guess numbers, dates, names or quotes; surface conflicting
  sources; name sources for searched claims; paraphrase instead of quoting.
- The agent must say so when it cannot see one of its own past answers instead
  of reconstructing it (no confabulated memory).

### 4. Memory: what you asked, and when
SQLite (`memory.db`, stdlib only, survives restarts). Every turn is stored with
a UTC unix timestamp and a session name. Two read paths:
- **Recent turns** (last 12) are replayed as ordinary chat messages for
  follow-ups. The window is trimmed so it always starts with a user turn
  (API requirement).
- **Question log**: the last 60 user questions, each as
  `[YYYY-MM-DD HH:MM] text` in the user's local timezone, truncated to 140
  chars, placed in the system prompt. This gives durable "what did I ask
  yesterday / first / last week" recall at a few hundred tokens, with no
  second tool (the brief allows only web search) and no embedding store.

The user's question is written to memory *before* the model call, so it is
logged even if the call fails.

## Trade-offs and limits
- Old *answers* are only available inside the 12-turn window; older ones are
  recalled by question only. Fine for the stated goal; a summarising layer
  would be the next step.
- The log caps at 60 questions. Beyond that, oldest entries drop out.
- Recall is prompt-based, not retrieval-based, so it is simple and fast but
  does not scale to thousands of questions.
- Search quality and citations come from the provider's search tool; we do not
  re-verify pages ourselves.

## Layout
- `agent.py`: prompt, streaming call, CLI
- `memory.py`: SQLite store, recent-turns and question-log readers
- `tests/test_memory.py`: memory behaviour (timezones, truncation, isolation)
