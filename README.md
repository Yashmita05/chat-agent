# Chat agent

A small chat agent with one tool (web search) that answers fast, avoids
guessing, and remembers what you asked and when. See [design.md](design.md).

```bash
pip install -r requirements.txt
export ANTHROPIC_API_KEY=...
python agent.py --tz Asia/Kolkata
```

Try: ask something current ("latest ..."), then later "what did I ask earlier
today?". Memory persists in `memory.db` across restarts. `/clear` forgets,
`/quit` exits. Set `AGENT_MODEL` to use a different model.

Tests: `pytest`
