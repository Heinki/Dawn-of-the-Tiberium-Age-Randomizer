param(
    [string]$OutputDirectory = $PSScriptRoot
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

# Use the same dependency bundling and deterministic archive format on every OS.
& python (Join-Path $PSScriptRoot "build_apworld.py") --output-directory $OutputDirectory
if ($LASTEXITCODE -ne 0) {
    throw "APWorld build failed with exit code $LASTEXITCODE."
}
