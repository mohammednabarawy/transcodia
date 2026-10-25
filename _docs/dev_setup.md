# Developer guide

## Environment

Use Python 3.10+ and a dedicated virtual environment. Install `requirements-dev.txt` for tests and packaging. The supported UI framework is PySide6; the media engine package has no Qt imports.

Install FFmpeg independently before running media tests or building. Typical setup commands are `winget install Gyan.FFmpeg` on Windows, `brew install ffmpeg-full` on macOS, or `sudo apt install ffmpeg` on Debian/Ubuntu. Linux Qt also needs the display/font libraries installed by the CI workflow.

On macOS, the standard Homebrew formula omits optional features used by this app. Use the full formula and expose its executable explicitly:

```bash
brew install ffmpeg-full
export FFMPEG_PATH="$(brew --prefix ffmpeg-full)/bin/ffmpeg"
```

This provides the subtitle, stabilization and Vorbis components exercised by the integration suite. The engine remains independently installed; it is not redistributed in the app archive.

```bash
python -m venv .venv
# Activate the environment for your shell.
python -m pip install -r requirements-dev.txt
python main.py
```

## Local executable configuration

The lookup order is `FFMPEG_PATH`, an application-local executable if one has been supplied by the operator, `ffmpeg_path` in `transcodia.local.json`, then `PATH`. Default distribution builds do not include a media engine.

Optional local configuration, excluded from Git:

```json
{"ffmpeg_path": "/path/to/ffmpeg"}
```

The source checkout, current working directory and packaged executable folder are checked for the local settings file. No other application's resource folders or document helpers are used.

## Verification commands

```bash
python main.py --version
python main.py --smoke-test
python main.py --verify-runtime artifacts/source-runtime.json
python scripts/run_tests.py --coverage
python scripts/render_screenshots.py
```

The runtime check creates synthetic image, PDF and media inputs and verifies actual outputs. It requires the declared libraries and a separately installed FFmpeg executable.

## Desktop bundles

```powershell
./scripts/windows_build.ps1
# Use an explicit engine for verification only:
./scripts/windows_build.ps1 -VerifyFfmpegPath /path/to/ffmpeg.exe
```

```bash
bash scripts/unix_build.sh /path/to/ffmpeg
```

The Windows script accepts `-SkipDependencyInstall` when dependencies are already installed in the active environment. Both build scripts run regression tests, collect installed dependency notices, create the desktop bundle and verify it outside the checkout before archiving it. The independently installed media engine used for verification is not copied into the archive.

Repeat a bundle check with:

```bash
python scripts/verify_bundle.py /path/to/Transcodia --ffmpeg /path/to/ffmpeg
```

PyInstaller's Windows dependency search can encounter same-named libraries from unrelated installations. The spec excludes the conflicting top-level ICU DLL and relies on the Windows system API Qt expects. The unused optional decorative font is excluded as well. Keep third-party notices with the bundle and complete applicable source-availability/replacement obligations before distributing native libraries publicly.

## CI and releases

CI tests the project on Windows, Linux and macOS. The macOS release matrix targets Apple silicon and Intel separately. Release workflows create drafts; they do not establish that every output has been tested locally.

Desktop publishing jobs remain disabled until the repository variable `ENABLE_DESKTOP_RELEASES` is set to `true`. Complete native-library licensing/source-availability review before enabling it. Ordinary source CI stays enabled.

Use `python scripts/bump_version.py --print` to read the version, `python scripts/bump_version.py 1.2.3` to set it, or the no-argument command to increment its minor version.

SonarCloud is optional. Configure repository variables `SONAR_ORGANIZATION` and `SONAR_PROJECT_KEY` plus the `SONAR_TOKEN` secret to enable its job. These values must match the actual analysis project.

Application source, generated branding, dependencies and native-library redistribution have separate rights. Do not remove required notices or infer legal clearance from a passing build.
