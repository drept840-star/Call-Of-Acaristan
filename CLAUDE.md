# OpenWolf

This project uses OpenWolf for context management. The always-on rules live in `.claude/rules/openwolf.md`; the hooks handle bookkeeping (anatomy index, memory log, read tracking) automatically.

For the full operating protocol (session handoff, memory discipline, bug logging), load the `openwolf` skill, or read `.wolf/OPENWOLF.md`. Regenerate the session handoff with `/handoff`.

# Delegated work

Send mechanical work (searches, gate runs, renders, sweeps) to subagents through the Agent tool. They run on Haiku 5.5 (`claude-haiku-5-5`, set by `CLAUDE_CODE_SUBAGENT_MODEL` in `.claude/settings.local.json`). Write each task as an exact, self-contained brief with the commands to run, and spot-check its claims (counts, pass/fail) before relying on them. Design and code stay on the main model. The DeepSeek worker (`ds-worker.mjs`) is retired for this project: it was unreliable.
