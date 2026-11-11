"""Chat agent: one tool (web search), streaming answers, timestamped memory.

Run:  python agent.py            (interactive chat)
      python agent.py --session work --tz Asia/Kolkata
Needs ANTHROPIC_API_KEY in the environment.
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime
from zoneinfo import ZoneInfo

import anthropic

from memory import Memory

# Fast model by default; override with AGENT_MODEL for harder questions.
MODEL = os.environ.get("AGENT_MODEL", "claude-haiku-5-5")

# The agent's ONLY tool: Anthropic's server-side web search.
# max_uses caps latency/cost: most questions need 0 or 1 searches.
WEB_SEARCH = {"type": "web_search_20250305", "name": "web_search", "max_uses": 3}

SYSTEM_TEMPLATE = """\
You are a fast, careful chat assistant. Your only tool is web search.

Current date and time: {now} ({tz}).

How to answer
- Answer from your own knowledge when the fact is stable (definitions, history, \
math, how things work). Do not search for those; it is slower and adds nothing.
- Search when the answer could have changed or you are unsure: news, prices, \
scores, "current/latest/still", who holds a role, versions, laws, anything dated \
after your training. One focused search is usually enough; search again only if \
the first result did not settle it. Use short, specific queries and put the \
current year in them when recency matters.
- Never guess a number, date, name or quote. If sources conflict or are thin, \
say so and give what is known.
- Lead with the answer in the first sentence, then the minimum support needed. \
Be brief unless asked for depth. Name your sources for searched claims, and \
paraphrase rather than quoting at length.

Memory
You remember this user's earlier questions. The log below lists what they asked \
and when (oldest first, local time). Use it to answer "what did I ask \
yesterday / earlier / first?", to resolve follow-ups like "and the previous \
one?", and to avoid repeating yourself. Only the questions are logged here; if \
asked about one of your past answers and you cannot see it in the conversation, \
say so instead of reconstructing it. Resolve relative dates ("yesterday", \
"last week") against the current date above.

Past questions:
{log}
"""


def build_system(mem: Memory, tz: str) -> list[dict]:
    now = datetime.now(ZoneInfo(tz)).strftime("%A, %d %B %Y, %H:%M")
    log = mem.question_log() or "(none yet; this is the first conversation)"
    # Cache the stable instructions; the volatile date/log goes after the breakpoint.
    head, tail = SYSTEM_TEMPLATE.split("Current date and time:", 1)
    return [
        {"type": "text", "text": head.strip(), "cache_control": {"type": "ephemeral"}},
        {"type": "text", "text": "Current date and time:" + tail.format(now=now, tz=tz, log=log)},
    ]


def extract_text(content) -> str:
    return "".join(b.text for b in content if getattr(b, "type", "") == "text").strip()


def ask(client: anthropic.Anthropic, mem: Memory, tz: str, question: str, out=sys.stdout) -> str:
    """Answer one question, streaming to `out`, and persist both turns."""
    messages = mem.recent_messages(12) + [{"role": "user", "content": question}]
    mem.add("user", question)  # log the question even if the call below fails

    with client.messages.stream(
        model=MODEL,
        max_tokens=1024,
        system=build_system(mem, tz),
        tools=[WEB_SEARCH],
        messages=messages,
    ) as stream:
        for text in stream.text_stream:
            out.write(text)
            out.flush()
        final = stream.get_final_message()

    answer = extract_text(final.content)
    if answer:
        mem.add("assistant", answer)
    out.write("\n")
    return answer


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--session", default="default", help="memory namespace")
    p.add_argument("--tz", default="UTC", help="IANA timezone, e.g. Asia/Kolkata")
    p.add_argument("--db", default="memory.db")
    args = p.parse_args()

    client = anthropic.Anthropic()
    mem = Memory(args.db, args.session, args.tz)
    print("Chat agent ready. /clear forgets, /quit exits.")
    while True:
        try:
            q = input("\nyou> ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not q:
            continue
        if q == "/quit":
            break
        if q == "/clear":
            mem.clear()
            print("memory cleared")
            continue
        try:
            print("agent> ", end="")
            ask(client, mem, args.tz, q)
        except anthropic.APIError as e:
            print(f"\n[error] {e}")


if __name__ == "__main__":
    main()
