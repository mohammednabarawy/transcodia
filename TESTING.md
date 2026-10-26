# Tests and verification scope

## Latest local result

The latest coverage run passed **287 tests in 29.16 seconds**, with **0 failures, 0 errors and 0 skips**. Source line coverage was **89.78%** and branch coverage **73.00%**. The PDF replacement and generated artwork were tested with the removed PDF engine absent from the isolated environment.

## Run

Install `requirements-dev.txt` in a virtual environment and install FFmpeg independently, then run:

```bash
python scripts/run_tests.py --coverage
```

Qt runs offscreen. Inputs are synthetic and live in pytest temporary folders. No user documents, real shutdowns, remote publishing or real external application launches are used in the test suite.

Reports are written to `artifacts/tests/`: `summary.json`, `pytest.log`, `junit.xml`, `coverage.json` and `coverage-html/index.html`. The summary contains the exact latest counts and coverage. Entry-point subprocesses and packaged execution are checked separately and do not contribute to the parent interpreter's coverage.

## Workflow coverage

| Area | Evidence |
| --- | --- |
| UI and localization | Actual Qt navigation, all tool routes, accepted/cancelled dialogs, Arabic/English switching and theme changes |
| Queue | Start through the actual conversion thread, real process pause/resume, cancellation/retry, failure isolation, complete error details, sizes above 2 GiB and restored controls |
| Inputs and settings | Files/folders/drops, duplicate filtering, validation, independent settings and queue persistence |
| Media | Real format conversions, decoded frames, trim/resize/rotate/crop, subtitles, watermarks and audio transforms |
| Advanced encoding | Actual two-pass and stabilization analysis plus final decoding |
| Join and mux | Duration/content checks, replacement-audio frequency, subtitle extraction and silent-video handling |
| Images | Reopened formats, transform pixels, dimensions, alpha handling and EXIF orientation |
| Documents | PDF text/table extraction, literal spreadsheet text, merge order, readable DOCX, DOCX text/table PDF rendering and atomic output publication |
| PDF workspace | Real rendered previews, duplicate handling, ordering and corrupt/encrypted/missing input rejection |
| Runtime and packaging | Resolver priority, missing dependencies, bundled FFmpeg/FFprobe and shared DLL inclusion, isolated executable checks and generated asset inclusion |
| Publication boundaries | Source-tree checks, generated asset hashes and no executable libraries in the public source tree |

The tests are under `transcodia_app/tests` and `transcodia_engine/tests`. Most UI tests manipulate real widgets rather than substituting the application logic. Hardware probing matrices are controlled tests; they are not certification of a physical GPU or driver.

An optional packaged check, `scripts/verify_bundle.py --media-source`, runs a five-second source clip through the main window's real queue and conversion thread with automatic encoder selection, decodes the result and checks the source was unchanged. This is additional local evidence, not a full-length media conversion. Automatic HEVC selection is also covered against hardware that supports only H.264.

## Limits

- Long or arbitrarily damaged media, incompatible stream combinations, low disk space, power events and every hardware driver are not exhaustively simulated.
- PDF/DOCX conversion focuses on text and tables. OCR, exact page-layout reproduction, complex-script shaping and embedded-media fidelity are not established by the current tests.
- An image/document job already executing may finish before a cooperative pause takes effect. Media processes use actual suspend/resume/cancel controls.
- Native player, recorder, downloader, disc and ISO tools are not implemented. Tests verify their clear unavailable responses.
- Offscreen widgets and screenshots do not prove native pixel behavior at every DPI or accessibility with assistive technology.
- Licensing and trademark clearance are not automated test assertions. See `THIRD_PARTY_NOTICES.md` and the asset creation record.
