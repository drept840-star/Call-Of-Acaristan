# OpenWolf

This project uses OpenWolf for context management. The always-on rules live in `.claude/rules/openwolf.md`; the hooks handle bookkeeping (anatomy index, memory log, read tracking) automatically.

For the full operating protocol (session handoff, memory discipline, bug logging), load the `openwolf` skill, or read `.wolf/OPENWOLF.md`. Regenerate the session handoff with `/handoff`.

# Delegated work

Never spawn subagents (the Agent tool, including `haiku-worker` and forks). They run on Haiku and draw on the Claude subscription, and a local PreToolUse hook blocks them. Send mechanical work (searches, gate runs, renders, sweeps) to the DeepSeek worker through Bash instead:

    node "$APPDATA/claude-code-router/ds-worker/ds-worker.mjs" [--edit] [--cwd DIR] [--max-turns N] "task"

It is a headless `claude -p` routed through the local claude-code-router to logfare's `deepseek-v4.1-flash-1017`, and it prints its answer on stdout. By default it can only read, search and run commands; `--edit` adds Edit and Write. Write the task as an exact, self-contained brief with the commands to run. Spot-check its claims (counts, pass/fail) before relying on them. Design and code stay on the main model. If the worker exits non-zero (3 means a missing key), do the work yourself or tell the user; never fall back to a Haiku subagent.
