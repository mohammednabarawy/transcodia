# Packaging verification

The distribution is a directory-based desktop application with dynamically loaded libraries. Windows packages contain Transcodia code, generated artwork, FFmpeg/FFprobe, their shared DLLs, other runtime libraries and their notices. No resource index for another application is used.

## Automated build checks

1. Run the source regression suite.
2. Collect the installed runtime dependency versions and available license/notice files.
3. Build the executable and include the project notice, third-party inventory and required license texts.
4. Launch outside the checkout with a temporary home and restricted PATH.
5. Require the Windows executable to select FFmpeg from inside the package, with no external executable override or engine on PATH.
6. Verify image conversion, PDF text/DOCX/XLSX content and MP4 encoding/decoding.
7. Create the platform archive after those checks pass.

The source audit also rejects executable libraries in the Git tree, machine-specific configuration, personal absolute paths and common secret-token patterns. Asset files have a recorded creation source and hashes. These checks provide evidence; they are not a copyright or trademark clearance opinion.

The runtime check additionally verifies all 24 app artwork files, a rendered PDF preview and DOCX-to-PDF text. An optional source-video check uses the main window's queue, conversion thread and automatic encoder selection to convert and decode a five-second clip, then verifies the original size and modification time remain unchanged. The report includes the selected encoder. See `TESTING.md` for measured source coverage.

## Local evidence

`artifacts/tests/summary.json` contains the latest regression result. `artifacts/bundle-verification.json` records the packaged runtime checks and bundled engine path. The engine inventory and upstream notices are generated under `artifacts/ffmpeg-notices` and included in the package. Build logs and generated outputs are excluded from Git.

Windows startup previously exposed an incompatible ICU library selected through PATH. The corrected spec excludes that collision and is covered by a regression test. The replacement PDF backend is tested without the removed engine installed in the build environment.

## Verification limits

Native macOS/Linux execution and actual GitHub Actions status require those runners. Real hardware encoders, native DPI/accessibility coverage, signing and notarization need additional verification. A local build does not imply a public binary release or completion of third-party redistribution obligations.
