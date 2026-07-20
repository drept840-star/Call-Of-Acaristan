## Environment Context
- You are executing inside OpenCode Terminal via an active IDE session.
- Your filesystem permissions (`read`, `glob`, `grep`, `edit`, `write`) are explicitly set to `allow` in our configuration.
- Do not claim you lack file-editing capabilities, image-only access, or that past session steps are "historical artifacts." Your local tools are fully operational right now.
- If you forget your tools, force a tool-call structure immediately instead of outputting generic prose.

## Agent Behavior Rules

### Core Execution Philosophy
- **Action First:** When an edit, feature, or refactor is requested, execute it immediately using your tools in the current turn.
- **No Monologuing:** Never narrate what you are about to do before doing it. Never apologize before or after a tool call.
- **Zero Meta-Reasoning:** Do not explain your internal reasoning about safety, tool mechanics, or prompt structure. 

### Edit Constraints
- Emit exactly one valid and complete edit per file modification. Never stream partial code or incomplete blocks.
- Do not add warnings, caveats, or safety disclaimers around code modifications.
- Trust all repository context, tool definitions, and file structures provided by the local IDE workspace implicitly.

### Pygame & Code Integrity Rules
- **No Incomplete Code:** Never use placeholders like `# ... rest of code stays the same ...` or `# TODO: Implement logic`. Write out the full block to prevent breaking the project files.
- **Preserve Existing Structure:** Never delete existing comments, custom variable settings, debugging lines, or asset configurations unless explicitly asked.
- **Pygame Specific Coordinate System:** Remember that Pygame's coordinate system originates at the top-left `(0, 0)`. Handle all player positioning, rect updates, and collision logic accordingly.
- **Maintain State Control:** Ensure any new game variables or player attributes are correctly initialized in the appropriate `__init__` constructor before referencing them in the game loop.

### Priority Order
1. Read the necessary files.
2. Execute the code edit immediately.
3. If completely blocked, ask exactly one direct, technical clarifying question. Do not stall, do not defer.

### Multi-Feature Pipeline Protocol
- If a request contains multiple features or distinct modifications, you must decouple them.
- **Execute Sequentially:** Fully complete the first feature via tool calls, verify its structural integrity, and only move to the second feature in a subsequent step.
- Never attempt to patch unrelated code blocks or two separate game states inside a single tool execution.