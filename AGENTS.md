# Transcodia — agent guide

Transcodia is a cross-platform desktop media converter (Python 3.10+, PySide6, FFmpeg).

## Directory overview

```
transcodia_app/      Qt application
  main.py            entry point (--version, --smoke-test)
  version.py         single source of truth for APP_NAME / APP_VERSION
  views/             windows and dialogs
  handlers/          image, document and probe helpers
  theme_manager.py   five Transcodia workspace palettes
  assets/            generated project mark, interface PNGs and creation manifest
  i18n.py            Arabic / English strings
transcodia_engine/   conversion engine (no Qt imports)
  models.py          task and parameter dataclasses
  engine.py          FFmpeg command construction
  filter_builder.py  -vf / -af / filter_complex builders
  worker.py          bounded-concurrency batch runner
  runtime_paths.py   FFmpeg and optional-resource lookup on any OS
scripts/             run_tests.py, bump_version.py, build and release scripts
packaging/           PyInstaller spec
_docs/               developer docs
.github/             CI, release workflows, Dependabot
```

## Rules

- `transcodia_engine` must not import `transcodia_app` or Qt.
- Never hardcode user names, drive letters or absolute install paths. Resolve tools through `transcodia_engine.runtime_paths`.
- Per-machine configuration goes in the git-ignored `transcodia.local.json`.
- Keep the version only in `transcodia_app/version.py`; change it with `scripts/bump_version.py`.
- Generated output (`artifacts/`, `build/`, `dist/`) is never committed.
- Interface icons are generated image assets. Use the built-in image generation tool for replacements; do not substitute code-drawn shapes or another application's resources.
- Preserve dependency notices. Windows packages include FFmpeg, its required DLLs and upstream notices; verify them with no external engine on PATH.
- Run `python scripts/audit_release_tree.py` against the staged source tree before publishing.
- Preserve existing comments and docstrings unrelated to your change.

## Verify before finishing

```bash
python scripts/run_tests.py
```

All tests must pass with no failures, errors or skips on a machine with FFmpeg. Add or update tests for any behavior you change; tests write only to pytest temp folders and run Qt offscreen.
