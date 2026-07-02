param(
    [string]$EnvFile
)

$ErrorActionPreference = "Stop"

$ProjectRoot = Resolve-Path (Join-Path $PSScriptRoot "..")

function Import-DotEnv {
    param([string]$Path)

    if (-not (Test-Path -LiteralPath $Path)) {
        return $false
    }

    foreach ($line in [System.IO.File]::ReadAllLines($Path, [System.Text.Encoding]::UTF8)) {
        $trimmed = $line.Trim()
        if ($trimmed.Length -eq 0 -or $trimmed.StartsWith("#")) {
            continue
        }

        $separator = $trimmed.IndexOf("=")
        if ($separator -le 0) {
            continue
        }

        $name = $trimmed.Substring(0, $separator).Trim()
        $value = $trimmed.Substring($separator + 1).Trim()

        if (($value.StartsWith('"') -and $value.EndsWith('"')) -or
            ($value.StartsWith("'") -and $value.EndsWith("'"))) {
            $value = $value.Substring(1, $value.Length - 2)
        }

        [Environment]::SetEnvironmentVariable($name, $value, "Process")
    }

    return $true
}

if (-not $EnvFile) {
    $localEnv = Join-Path $ProjectRoot ".env.local"
    $defaultEnv = Join-Path $ProjectRoot ".env"

    if (Test-Path -LiteralPath $localEnv) {
        $EnvFile = $localEnv
    } else {
        $EnvFile = $defaultEnv
    }
}

$loaded = Import-DotEnv $EnvFile
if ($loaded) {
    Write-Host "Loaded env file: $EnvFile"
} else {
    Write-Host "Env file not found: $EnvFile"
}

Set-Location $ProjectRoot
python -m uvicorn app.main:app --host 0.0.0.0 --port 8001
