Quick setup for Anthropic-compatible agent keys

1) Create a local `.env` from `.env.example` and paste your key (do NOT commit `.env`).

2) To set variables for the current PowerShell session (temporary):

```powershell
$env:ANTHROPIC_BASE_URL = "https://unlimited.surf"
$env:ANTHROPIC_AUTH_TOKEN = "PASTE_YOUR_KEY_HERE"
$env:ANTHROPIC_API_KEY = "PASTE_YOUR_KEY_HERE"
$env:ANTHROPIC_MODEL = "claude-opus-4-7-20260101"
```

3) To persist variables for your user account, run the helper script and enter the key when prompted:

```powershell
.\\scripts\\setup_env.ps1
```

Or pass the key as an argument (be careful: may be visible in process lists):

```powershell
.\\scripts\\setup_env.ps1 -ApiKey "PASTE_YOUR_KEY_HERE"
```

4) Verification: restart your terminal, then run your agent (`claude`) or a test command. If you have a CLI, simply run `claude`.

Security notes:
- Never commit real keys. Use `.env` + `.gitignore`, Windows Credential Manager, or a secret manager.
- Rotate the key if it was ever exposed.
