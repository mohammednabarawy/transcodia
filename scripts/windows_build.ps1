# Build the Transcodia desktop bundle on Windows.
# Usage: ./scripts/windows_build.ps1 [-VerifyFfmpegPath path/to/ffmpeg.exe]
# Output: dist/Transcodia/Transcodia.exe and dist/Transcodia-<version>-windows-x64.zip
param([string]$VerifyFfmpegPath = "", [switch]$SkipDependencyInstall)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

$version = (python scripts/bump_version.py --print).Trim()
if ($LASTEXITCODE -ne 0) { throw "Could not read application version" }
Write-Host "Building Transcodia $version for Windows"

if (-not $SkipDependencyInstall) {
    python -m pip install -r requirements-dev.txt
    if ($LASTEXITCODE -ne 0) { throw "Dependency installation failed" }
}
if (-not $VerifyFfmpegPath) { $VerifyFfmpegPath = (python -c "from transcodia_engine.runtime_paths import find_ffmpeg; print(find_ffmpeg())").Trim() }

python scripts/run_tests.py --report-dir artifacts/build-tests
if ($LASTEXITCODE -ne 0) { throw "Regression tests failed" }
python scripts/collect_notices.py
if ($LASTEXITCODE -ne 0) { throw "Dependency notice collection failed" }

python -m PyInstaller packaging/transcodia.spec --noconfirm --clean
if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed" }

$exe = Join-Path $root "dist/Transcodia/Transcodia.exe"
if (-not (Test-Path $exe)) { throw "Expected $exe was not produced" }
python scripts/verify_bundle.py $exe --ffmpeg $VerifyFfmpegPath
if ($LASTEXITCODE -ne 0) { throw "Packaged conversion verification failed" }

$zip = Join-Path $root "dist/Transcodia-$version-windows-x64.zip"
if (Test-Path $zip) { Remove-Item $zip }
Compress-Archive -Path (Join-Path $root "dist/Transcodia") -DestinationPath $zip
Write-Host "Built $zip"
