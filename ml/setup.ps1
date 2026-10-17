param(
    [string]$PythonVersion = "3.14",
    [switch]$ProvisionModel
)

$ErrorActionPreference = "Stop"
$MlProjectRoot = Split-Path -Parent $PSScriptRoot
$MlPython = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"

Push-Location -LiteralPath $MlProjectRoot
try {
    if (-not (Test-Path -LiteralPath $MlPython)) {
        & py "-$PythonVersion" -m venv (Join-Path $PSScriptRoot ".venv")
        if ($LASTEXITCODE -ne 0) { throw "Could not create the ML virtual environment." }
    }
    & $MlPython -m pip install -r (Join-Path $PSScriptRoot "requirements-lock.txt")
    if ($LASTEXITCODE -ne 0) { throw "Pinned ML dependency installation failed." }
    & $MlPython -m pip check
    if ($LASTEXITCODE -ne 0) { throw "ML dependency validation failed." }
    if ($ProvisionModel) {
        & $MlPython -m ml.provision --download
        if ($LASTEXITCODE -ne 0) { throw "Pinned model provisioning failed; existing artifacts are preserved." }
    }
} finally {
    Pop-Location
}
