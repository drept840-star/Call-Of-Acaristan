# OpenWolf

This project uses OpenWolf for context management. The always-on rules live in `.claude/rules/openwolf.md`; the hooks handle bookkeeping (anatomy index, memory log, read tracking) automatically.

For the full operating protocol (session handoff, memory discipline, bug logging), load the `openwolf` skill, or read `.wolf/OPENWOLF.md`. Regenerate the session handoff with `/handoff`.

# Subagents

Always run subagents on Haiku: pass `model: "haiku"` on every Agent call, or use the `haiku-worker` agent. Never pick Opus or Sonnet for a subagent unless the user explicitly asks for it. Never use `subagent_type: "fork"` (forks always inherit the main model).
