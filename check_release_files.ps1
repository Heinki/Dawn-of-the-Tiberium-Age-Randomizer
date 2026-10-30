param(
    [string]$ExpectedVersion = ""
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$repositoryRoot = $PSScriptRoot
$launcherVersionPath = Join-Path $repositoryRoot "randomizer\core\version.py"
$apworldPath = Join-Path $repositoryRoot "Archipelago\dta.apworld"
$versionPattern = '\d+\.\d+(?:\.\d+)?'

function Read-RequiredMatch {
    param(
        [string]$Path,
        [string]$Pattern,
        [string]$Label
    )

    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        throw "$Label is missing: $Path"
    }
    $content = Get-Content -LiteralPath $Path -Raw
    $match = [Regex]::Match($content, $Pattern)
    if (-not $match.Success) {
        throw "Unable to read $Label from $Path"
    }
    return $match.Groups['version'].Value
}

$launcherVersion = Read-RequiredMatch `
    -Path $launcherVersionPath `
    -Pattern ('APP_VERSION\s*=\s*[''"](?<version>{0})[''"]' -f $versionPattern) `
    -Label "launcher version"
$worldVersion = ((@($launcherVersion.Split('.')) + @('0', '0'))[0..2] -join '.')
$archipelagoVersion = Read-RequiredMatch `
    -Path $launcherVersionPath `
    -Pattern ('ARCHIPELAGO_VERSION\s*=\s*[''"](?<version>{0})[''"]' -f $versionPattern) `
    -Label "Archipelago version"

if ($ExpectedVersion) {
    $normalizedExpectedVersion = $ExpectedVersion -replace '^[vV]', ''
    if ($normalizedExpectedVersion -notmatch "^$versionPattern$") {
        throw "Expected release version is invalid: $ExpectedVersion"
    }
    if ($launcherVersion -ne $normalizedExpectedVersion) {
        throw (
            "Release tag version $normalizedExpectedVersion does not match " +
            "source version $launcherVersion."
        )
    }
}

if (-not (Test-Path -LiteralPath $apworldPath -PathType Leaf)) {
    throw "Committed APWorld is missing: $apworldPath"
}

$generatedDirectory = Join-Path (
    [IO.Path]::GetTempPath()
) ("dta-apworld-check-" + [Guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Path $generatedDirectory | Out-Null
try {
    & python (Join-Path $repositoryRoot "Archipelago\build_apworld.py") `
        --output-directory $generatedDirectory | Out-Null
    if ($LASTEXITCODE -ne 0) {
        throw "APWorld verification build failed with exit code $LASTEXITCODE."
    }
    $generatedApworld = Join-Path $generatedDirectory "dta.apworld"
    $committedHash = (
        Get-FileHash -LiteralPath $apworldPath -Algorithm SHA256
    ).Hash.ToLowerInvariant()
    # ZIP platform headers and compression differ between Windows and Linux.
    # Require identical packaged paths and bytes, independent of the container.
    $compareArchives = @'
import sys
from zipfile import ZipFile

with ZipFile(sys.argv[1]) as committed, ZipFile(sys.argv[2]) as generated:
    committed_names = committed.namelist()
    generated_names = generated.namelist()
    if (len(set(committed_names)) != len(committed_names)
            or len(set(generated_names)) != len(generated_names)):
        raise SystemExit('APWorld contains duplicate archive paths.')
    if set(committed_names) != set(generated_names):
        raise SystemExit('Committed APWorld file list differs from the source build.')
    for name in sorted(generated_names):
        if committed.read(name) != generated.read(name):
            raise SystemExit('Committed APWorld content differs from source: ' + name)
print('Committed APWorld contents match the source build.')
'@
    & python -c $compareArchives $apworldPath $generatedApworld
    if ($LASTEXITCODE -ne 0) {
        throw "Committed APWorld does not match the source build."
    }
}
finally {
    Remove-Item -LiteralPath $generatedDirectory -Recurse -Force
}

Add-Type -AssemblyName System.IO.Compression
Add-Type -AssemblyName System.IO.Compression.FileSystem

$archive = [IO.Compression.ZipFile]::OpenRead($apworldPath)
try {
    $manifestEntry = $archive.GetEntry('dta/archipelago.json')
    if ($null -eq $manifestEntry) {
        throw "Committed APWorld manifest is missing."
    }
    $manifestReader = [IO.StreamReader]::new(
        $manifestEntry.Open(),
        [Text.UTF8Encoding]::new($false)
    )
    try {
        $packagedManifest = $manifestReader.ReadToEnd() | ConvertFrom-Json
    }
    finally {
        $manifestReader.Dispose()
    }

    if (
        [string]$packagedManifest.world_version -ne $worldVersion -or
        [int]$packagedManifest.compatible_version -ne 7 -or
        [int]$packagedManifest.version -ne 8 -or
        [string]$packagedManifest.maximum_ap_version -ne $archipelagoVersion
    ) {
        throw "Committed APWorld manifest is stale or incompatible."
    }
}
finally {
    $archive.Dispose()
}

Write-Output ([pscustomobject]@{
    launcher_version = $launcherVersion
    apworld_version = $worldVersion
    apworld = $apworldPath
    archive_sha256 = $committedHash
})
