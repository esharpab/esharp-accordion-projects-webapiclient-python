<#
.SYNOPSIS
    Build, test, and publish the AccordionQ2 Python client package.

.DESCRIPTION
    Comprehensive script for managing the accordionq2 Python package lifecycle:
      - Environment setup (venv + dependencies)
      - Version management (syncs pyproject.toml and __init__.py)
      - Testing (unit + optional integration)
      - Building (sdist + wheel)
      - Publishing to PyPI or a private feed

.PARAMETER Action
    What to do. One or more of: Setup, Test, Build, Publish, Docs, All.
    Docs starts a local MkDocs dev server at http://127.0.0.1:8000.
    Default: Setup

.PARAMETER Version
    Semantic version string to set before building, e.g. "1.2.0".
    If omitted, the current version in pyproject.toml is used.

.PARAMETER Repository
    Target repository for publishing.
      pypi        - Public PyPI (default)
      testpypi    - PyPI test server
      github      - GitHub Packages
      <url>       - Any custom repository URL

.PARAMETER ApiKey
    API token for the target repository.
    Can also be set via PYPI_API_KEY or TWINE_PASSWORD env vars.

.PARAMETER SkipTests
    Skip running tests before building/publishing.

.EXAMPLE
    .\publish-python-package.ps1 -Action Setup
    # Creates venv and installs dev dependencies.

.EXAMPLE
    .\publish-python-package.ps1 -Action All -Version 1.2.0
    # Setup, test, build, and publish version 1.2.0 to PyPI.

.EXAMPLE
    .\publish-python-package.ps1 -Action Build -Version 2.0.0
    # Just bump version and build the wheel + sdist.

.EXAMPLE
    .\publish-python-package.ps1 -Action Publish -Repository testpypi -ApiKey pypi-xxxx
    # Publish existing dist/ to the PyPI test server.
#>

[CmdletBinding()]
param(
    [ValidateSet("Setup", "Test", "Build", "Publish", "Docs", "All")]
    [string[]]$Action = @("Setup"),

    [string]$Version,

    [string]$Repository = "pypi",

    [string]$ApiKey = "pypi-AgEIcHlwaS5vcmcCJGRkOWZhN2JhLWRjMzMtNDI2NS04MGRkLTU5OTlmNDBjNmE2NQACKlszLCI0YmNkODlhMi02MWVhLTQyYWItYThmMC0zNGEwYjE0ZmY3MzUiXQAABiCL3iWwvHC5EJjVfavJ2xvWniHK9Zn9BxzvYb1TvifaKw",

    [switch]$SkipTests
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

# ── Paths ────────────────────────────────────────────────────────────────────
$ProjectRoot   = $PSScriptRoot
$VenvDir       = Join-Path $ProjectRoot ".venv"
$DistDir       = Join-Path $ProjectRoot "dist"
$PyProject     = Join-Path $ProjectRoot "pyproject.toml"
$InitPy        = Join-Path $ProjectRoot "accordionq2" "__init__.py"

# ── Helpers ──────────────────────────────────────────────────────────────────
function Write-Step([string]$msg) {
    Write-Host ""
    Write-Host "── $msg ──" -ForegroundColor Cyan
}

function Assert-ExitCode([string]$step) {
    if ($LASTEXITCODE -ne 0) {
        Write-Host "FAILED: $step (exit code $LASTEXITCODE)" -ForegroundColor Red
        exit $LASTEXITCODE
    }
}

function Get-Python {
    # Prefer the venv python if it exists
    $venvPy = Join-Path $VenvDir "Scripts" "python.exe"
    if (Test-Path $venvPy) { return $venvPy }

    # Fall back to system python
    foreach ($cmd in @("python3", "python")) {
        $found = Get-Command $cmd -ErrorAction SilentlyContinue
        if ($found) { return $found.Source }
    }
    Write-Host "ERROR: Python not found. Install Python 3.8+ and ensure it is on PATH." -ForegroundColor Red
    exit 1
}

function Get-CurrentVersion {
    $content = Get-Content $PyProject -Raw
    if ($content -match 'version\s*=\s*"([^"]+)"') {
        return $Matches[1]
    }
    Write-Host "ERROR: Could not read version from pyproject.toml" -ForegroundColor Red
    exit 1
}

function Set-PackageVersion([string]$newVersion) {
    Write-Step "Setting version to $newVersion"

    # Update pyproject.toml
    $toml = Get-Content $PyProject -Raw
    $toml = $toml -replace '(version\s*=\s*")[^"]+"', "`${1}$newVersion`""
    [System.IO.File]::WriteAllText($PyProject, $toml)
    Write-Host "  Updated pyproject.toml"

    # Update __init__.py
    $init = Get-Content $InitPy -Raw
    $init = $init -replace '(__version__\s*=\s*")[^"]+"', "`${1}$newVersion`""
    [System.IO.File]::WriteAllText($InitPy, $init)
    Write-Host "  Updated __init__.py"
}

# ── Actions ──────────────────────────────────────────────────────────────────

function Invoke-Setup {
    Write-Step "Setting up Python environment"

    # If venv already exists, use its python; otherwise find system python
    $venvPy = Join-Path $VenvDir "Scripts" "python.exe"
    if (Test-Path $venvPy) {
        $sysPython = $venvPy
    } else {
        $sysPython = $null
        foreach ($cmd in @("python3", "python")) {
            $found = Get-Command $cmd -ErrorAction SilentlyContinue
            if ($found) { $sysPython = $found.Source; break }
        }
        if (-not $sysPython) {
            Write-Host "ERROR: Python not found on PATH and no existing .venv found." -ForegroundColor Red
            Write-Host "  Install Python 3.8+ and ensure it is on PATH, or create a .venv manually." -ForegroundColor Yellow
            exit 1
        }
    }

    # Show Python version
    & $sysPython --version
    Assert-ExitCode "python --version"

    # Create venv if missing
    if (-not (Test-Path $VenvDir)) {
        Write-Host "  Creating virtual environment in .venv ..."
        & $sysPython -m venv $VenvDir
        Assert-ExitCode "create venv"
    } else {
        Write-Host "  Virtual environment already exists."
    }

    $py = Get-Python

    # Upgrade pip
    Write-Host "  Upgrading pip ..."
    & $py -m pip install --upgrade pip --quiet
    Assert-ExitCode "pip upgrade"

    # Install build + publish tools
    Write-Host "  Installing build tools (build, twine) ..."
    & $py -m pip install --upgrade build twine --quiet
    Assert-ExitCode "install build tools"

    # Install package in editable mode with dev dependencies
    Write-Host "  Installing package in editable mode with dev deps ..."
    & $py -m pip install -e "$ProjectRoot[dev]" --quiet
    Assert-ExitCode "pip install -e .[dev]"

    Write-Host "  Setup complete." -ForegroundColor Green
}

function Invoke-Test {
    Write-Step "Running tests"

    $py = Get-Python

    # Run unit tests first (if any exist)
    Write-Host "  Running unit tests ..."
    & $py -m pytest (Join-Path $ProjectRoot "tests") -v --tb=short -m "not integration and not performance"
    if ($LASTEXITCODE -eq 5) {
        Write-Host "  No unit tests found (all tests are integration/performance)." -ForegroundColor Yellow
    } elseif ($LASTEXITCODE -ne 0) {
        Assert-ExitCode "pytest (unit)"
    }

    # Run integration tests (require hardware — skip with -SkipTests)
    Write-Host "  Running integration tests ..."
    & $py -m pytest (Join-Path $ProjectRoot "tests") -v --tb=short -m "integration"
    Assert-ExitCode "pytest (integration)"

    Write-Host "  All tests passed." -ForegroundColor Green
}

function Invoke-Build {
    $currentVersion = Get-CurrentVersion
    Write-Step "Building package (version $currentVersion)"

    $py = Get-Python

    # Clean previous builds
    if (Test-Path $DistDir) {
        Write-Host "  Cleaning dist/ ..."
        Remove-Item $DistDir -Recurse -Force
    }

    $eggInfo = Join-Path $ProjectRoot "accordionq2.egg-info"
    if (Test-Path $eggInfo) {
        Remove-Item $eggInfo -Recurse -Force
    }

    # Build sdist + wheel
    Write-Host "  Building sdist and wheel ..."
    & $py -m build $ProjectRoot
    Assert-ExitCode "python -m build"

    # Show what was produced
    Write-Host ""
    Write-Host "  Built artifacts:" -ForegroundColor Green
    Get-ChildItem $DistDir | ForEach-Object {
        $size = [math]::Round($_.Length / 1KB, 1)
        Write-Host "    $($_.Name)  (${size} KB)"
    }
}

function Invoke-Publish {
    $currentVersion = Get-CurrentVersion
    Write-Step "Publishing version $currentVersion"

    $py = Get-Python

    if (-not (Test-Path $DistDir) -or (Get-ChildItem $DistDir).Count -eq 0) {
        Write-Host "  No artifacts in dist/. Run with -Action Build first." -ForegroundColor Yellow
        exit 1
    }

    # Resolve API key
    $token = $ApiKey
    if (-not $token) { $token = $env:PYPI_API_KEY }
    if (-not $token) { $token = $env:TWINE_PASSWORD }

    # Resolve repository URL
    $repoArgs = @()
    switch ($Repository.ToLower()) {
        "pypi" {
            # Default, no extra args needed
        }
        "testpypi" {
            $repoArgs += "--repository-url"
            $repoArgs += "https://test.pypi.org/legacy/"
        }
        "github" {
            $owner = "esharpab"
            $repoArgs += "--repository-url"
            $repoArgs += "https://upload.pypi.org/legacy/"  # GitHub Packages uses standard PyPI upload
            Write-Host "  Note: For GitHub Packages, use a Personal Access Token as the API key." -ForegroundColor Yellow
        }
        default {
            # Treat as custom URL
            $repoArgs += "--repository-url"
            $repoArgs += $Repository
        }
    }

    # Build twine command
    $twineArgs = @("upload") + $repoArgs + @("$DistDir/*")

    if ($token) {
        $env:TWINE_USERNAME = "__token__"
        $env:TWINE_PASSWORD = $token
        Write-Host "  Using API token for authentication."
    } else {
        Write-Host "  No API key provided. Twine will prompt for credentials." -ForegroundColor Yellow
        Write-Host "  Tip: pass -ApiKey, or set PYPI_API_KEY env var." -ForegroundColor Yellow
    }

    Write-Host "  Uploading to: $Repository ..."
    & $py -m twine @twineArgs
    Assert-ExitCode "twine upload"

    # Cleanup env vars
    Remove-Item Env:\TWINE_USERNAME -ErrorAction SilentlyContinue
    Remove-Item Env:\TWINE_PASSWORD -ErrorAction SilentlyContinue

    Write-Host ""
    Write-Host "  Published accordionq2 $currentVersion" -ForegroundColor Green
    if ($Repository.ToLower() -eq "pypi") {
        Write-Host "  Install with: pip install accordionq2==$currentVersion"
    } elseif ($Repository.ToLower() -eq "testpypi") {
        Write-Host "  Install with: pip install --index-url https://test.pypi.org/simple/ accordionq2==$currentVersion"
    }
}

function Invoke-Docs {
    Write-Step "Building documentation (MkDocs)"

    $py = Get-Python

    # Install mkdocs-material if not already present
    Write-Host "  Ensuring mkdocs-material is installed ..."
    & $py -m pip install --upgrade mkdocs-material --quiet
    Assert-ExitCode "install mkdocs-material"

    $mkdocsYml = Join-Path $ProjectRoot "mkdocs.yml"
    if (-not (Test-Path $mkdocsYml)) {
        Write-Host "  ERROR: mkdocs.yml not found at $mkdocsYml" -ForegroundColor Red
        exit 1
    }

    Write-Host "  Starting local documentation server ..."
    Write-Host "  Open http://127.0.0.1:8000 in your browser." -ForegroundColor Cyan
    Write-Host "  Press Ctrl+C to stop." -ForegroundColor Yellow
    Push-Location $ProjectRoot
    try {
        & $py -m mkdocs serve
    } finally {
        Pop-Location
    }
}

# ── Main ─────────────────────────────────────────────────────────────────────

Write-Host "========================================" -ForegroundColor White
Write-Host " AccordionQ2 Python Package Manager" -ForegroundColor White
Write-Host "========================================" -ForegroundColor White

# Expand "All" into the ordered action list
if ($Action -contains "All") {
    $Action = @("Setup", "Test", "Build", "Publish")
    if ($SkipTests) {
        $Action = @("Setup", "Build", "Publish")
    }
}

# Apply version bump early (before build/test)
if ($Version) {
    Set-PackageVersion $Version
}

foreach ($a in $Action) {
    switch ($a) {
        "Setup"   { Invoke-Setup }
        "Test"    { Invoke-Test }
        "Build"   { Invoke-Build }
        "Publish" { Invoke-Publish }
        "Docs"    { Invoke-Docs }
    }
}

Write-Host ""
Write-Host "Done." -ForegroundColor Green
