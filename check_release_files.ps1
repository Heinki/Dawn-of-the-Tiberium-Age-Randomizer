param(
    [string]$ExpectedVersion = ""
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$repositoryRoot = $PSScriptRoot
$launcherVersionPath = Join-Path $repositoryRoot "randomizer\core\version.py"
$worldSourceDirectory = Join-Path $repositoryRoot "Archipelago\APWorld\dta"
$worldManifestPath = Join-Path $worldSourceDirectory "archipelago.json"
$worldContractPath = Join-Path $worldSourceDirectory "manifest.py"
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

function Get-StreamSha256 {
    param([System.IO.Stream]$Stream)

    $sha256 = [Security.Cryptography.SHA256]::Create()
    try {
        return ([BitConverter]::ToString(
            $sha256.ComputeHash($Stream)
        )).Replace('-', '').ToLowerInvariant()
    }
    finally {
        $sha256.Dispose()
    }
}

$launcherVersion = Read-RequiredMatch `
    -Path $launcherVersionPath `
    -Pattern ('APP_VERSION\s*=\s*[''"](?<version>{0})[''"]' -f $versionPattern) `
    -Label "launcher version"
$worldContractVersion = Read-RequiredMatch `
    -Path $worldContractPath `
    -Pattern ('RANDOMIZER_VERSION\s*=\s*[''"](?<version>{0})[''"]' -f $versionPattern) `
    -Label "APWorld launcher compatibility version"

if (-not (Test-Path -LiteralPath $worldManifestPath -PathType Leaf)) {
    throw "APWorld source manifest is missing: $worldManifestPath"
}
$worldManifest = Get-Content -LiteralPath $worldManifestPath -Raw |
    ConvertFrom-Json
$worldVersion = [string]$worldManifest.world_version

if ($launcherVersion -ne $worldVersion -or $launcherVersion -ne $worldContractVersion) {
    throw (
        "Release versions differ: launcher=$launcherVersion, " +
        "APWorld=$worldVersion, compatibility=$worldContractVersion."
    )
}

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

Add-Type -AssemblyName System.IO.Compression
Add-Type -AssemblyName System.IO.Compression.FileSystem

$archive = [IO.Compression.ZipFile]::OpenRead($apworldPath)
try {
    $sourcePrefix = $worldSourceDirectory.TrimEnd('\', '/') + '\'
    $sourceFiles = @(
        Get-ChildItem -LiteralPath $worldSourceDirectory -File -Recurse |
            Where-Object {
                $_.Name -ne 'archipelago.json' -and
                $_.Extension -ne '.pyc' -and
                $_.FullName -notmatch '[\\/]__pycache__[\\/]'
            }
    )
    $expectedEntries = @(
        $sourceFiles | ForEach-Object {
            'dta/' + $_.FullName.Substring($sourcePrefix.Length).Replace('\', '/')
        }
        'dta/archipelago.json'
    ) | Sort-Object
    $actualEntries = @($archive.Entries.FullName) | Sort-Object
    $entryDifference = @(Compare-Object $expectedEntries $actualEntries)
    if ($entryDifference.Count -gt 0) {
        throw "Committed APWorld file list does not match APWorld source files."
    }

    foreach ($sourceFile in $sourceFiles) {
        $entryName = (
            'dta/' +
            $sourceFile.FullName.Substring($sourcePrefix.Length).Replace('\', '/')
        )
        $entry = $archive.GetEntry($entryName)
        $entryStream = $entry.Open()
        try {
            $entryHash = Get-StreamSha256 $entryStream
        }
        finally {
            $entryStream.Dispose()
        }
        $sourceHash = (
            Get-FileHash -LiteralPath $sourceFile.FullName -Algorithm SHA256
        ).Hash.ToLowerInvariant()
        if ($entryHash -ne $sourceHash) {
            throw "Committed APWorld contains stale file: $entryName"
        }
    }

    $manifestEntry = $archive.GetEntry('dta/archipelago.json')
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
        [int]$packagedManifest.version -ne 7 -or
        [string]$packagedManifest.maximum_ap_version -ne '0.6.7'
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
    source_files_verified = $sourceFiles.Count + 1
})
