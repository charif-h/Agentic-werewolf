# Download the model used by the game into Ollama (Windows).
#   .\scripts\pull_model.ps1            -> model from LLM_MODEL (.env or environment), default gemma3:4b
#   .\scripts\pull_model.ps1 gemma3:1b  -> a specific model
param([string]$Model)

$root = Split-Path -Parent $PSScriptRoot
if (-not $Model -and (Test-Path "$root\.env")) {
    $line = Select-String -Path "$root\.env" -Pattern '^LLM_MODEL=' | Select-Object -Last 1
    if ($line) { $Model = ($line.Line -split '=', 2)[1].Trim('"', "'", ' ') }
}
if (-not $Model) { $Model = if ($env:LLM_MODEL) { $env:LLM_MODEL } else { 'gemma3:4b' } }

if (-not (Get-Command ollama -ErrorAction SilentlyContinue)) {
    Write-Error "Ollama was not found. Install it from https://ollama.com (or: winget install Ollama.Ollama)"
    exit 1
}
Write-Host "Pulling $Model ..."
ollama pull $Model
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
Write-Host "Done. Check with: ollama list"
