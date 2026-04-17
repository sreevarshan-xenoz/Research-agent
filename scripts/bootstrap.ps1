param(
    [switch]$Dev
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

if (-not (Test-Path ".venv")) {
    python -m venv .venv
}

. .\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip

if ($Dev) {
    pip install -e .[dev]
} else {
    pip install -e .
}

Write-Host "Bootstrap complete." -ForegroundColor Green
