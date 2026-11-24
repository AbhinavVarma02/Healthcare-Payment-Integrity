param(
    [Parameter(Mandatory)][ValidatePattern('^[a-z0-9-]+$')][string]$Label,
    [string]$Ref = 'HEAD'
)

$ErrorActionPreference = 'Stop'
$repo = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$cache = Join-Path $repo '.cache'
$archive = Join-Path $cache "$Label.zip"
$checkout = Join-Path $cache $Label
$previousUv = $env:UV_CACHE_DIR
$previousNpm = $env:npm_config_cache
$previousPython = $env:PYTHONPATH
$previousCoverage = $env:COVERAGE_FILE
$env:UV_CACHE_DIR = Join-Path $cache 'uv'
$env:npm_config_cache = Join-Path $cache 'npm'

function Invoke-Gate {
    param([string]$Executable, [string[]]$Arguments)
    & $Executable @Arguments
    if ($LASTEXITCODE -ne 0) { throw "$Executable exited $LASTEXITCODE" }
}

New-Item -ItemType Directory -Force $cache | Out-Null
if ((Test-Path -LiteralPath $archive) -or (Test-Path -LiteralPath $checkout)) {
    throw 'Choose an unused archive label to keep prior evidence.'
}
Push-Location $repo
try {
    $tree = git rev-parse "$Ref^{tree}"
    if ($LASTEXITCODE -ne 0) { throw 'Cannot resolve the requested release tree.' }
    Invoke-Gate git @('archive', '--format=zip', "--output=$archive", $tree)
    Expand-Archive -LiteralPath $archive -DestinationPath $checkout
    Push-Location $checkout
    try {
        New-Item -ItemType Directory -Force .cache,artifacts | Out-Null
        $env:PYTHONPATH = 'src'
        $env:COVERAGE_FILE = '.cache/release.coverage'
        Invoke-Gate uv @('sync', '--offline', '--locked', '--python', '3.13.2')
        Invoke-Gate .venv/Scripts/python.exe @('scripts/fixture_smoke.py')
        Invoke-Gate .venv/Scripts/python.exe @('-m', 'coverage', 'run', '--branch', '--source=payment_integrity',
            '-m', 'pytest', '-q', '--basetemp', '.cache/pytest', '--junitxml', 'artifacts/pytest.xml')
        Invoke-Gate .venv/Scripts/python.exe @('-m', 'coverage', 'json', '-o', 'artifacts/python-coverage.json')
        Invoke-Gate .venv/Scripts/ruff.exe @('check', 'src', 'tests', 'scripts')
        Invoke-Gate .venv/Scripts/mypy.exe @('--ignore-missing-imports', '--explicit-package-bases',
            'src/payment_integrity', 'scripts')
        Invoke-Gate npm @('--prefix', 'web', 'ci', '--offline', '--ignore-scripts')
        Invoke-Gate npm @('--prefix', 'web', 'run', 'test:coverage')
        Invoke-Gate npm @('--prefix', 'web', 'run', 'build')
        Invoke-Gate .venv/Scripts/python.exe @('-m', 'payment_integrity.publication', 'export')
        $proof = [ordered]@{
            tree = $tree
            scope = 'Offline clean source archive with cached locked dependencies'
            files = Get-Content artifacts/release-audit.json -Raw | ConvertFrom-Json -AsHashtable
        }
        $proof | ConvertTo-Json -Depth 5 | Set-Content artifacts/clean-build.json
    } finally {
        Pop-Location
    }
} finally {
    Pop-Location
    $env:UV_CACHE_DIR = $previousUv
    $env:npm_config_cache = $previousNpm
    $env:PYTHONPATH = $previousPython
    $env:COVERAGE_FILE = $previousCoverage
}
