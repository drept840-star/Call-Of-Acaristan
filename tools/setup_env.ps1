Param(
    [Parameter(Mandatory=$false)][string]$ApiKey
)

if (-not (Test-Path -Path (Join-Path $PSScriptRoot '..')) ) {
    # ensure script is running from repo; not required but harmless
}

if (-not $ApiKey) {
    $secure = Read-Host -AsSecureString "Enter Anthropic API key"
    $ApiKey = [Runtime.InteropServices.Marshal]::PtrToStringAuto([Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure))
}

setx ANTHROPIC_BASE_URL "https://unlimited.surf"
setx ANTHROPIC_AUTH_TOKEN $ApiKey
setx ANTHROPIC_API_KEY $ApiKey
setx ANTHROPIC_MODEL "claude-opus-4-7-20260101"

Write-Host "Environment variables written with setx. Restart your terminal to pick them up."
