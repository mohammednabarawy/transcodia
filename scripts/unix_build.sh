#!/usr/bin/env bash
# Build the Transcodia desktop bundle on macOS or Linux.
# Usage: ./scripts/unix_build.sh [path/to/ffmpeg]
# Output: macOS -> dist/Transcodia-<version>-macos-<arch>.zip (contains Transcodia.app)
#         Linux -> dist/Transcodia-<version>-linux-<arch>.tar.gz
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

VERSION="$(python3 scripts/bump_version.py --print)"
ARCH="$(uname -m)"
echo "Building Transcodia ${VERSION} for $(uname -s)/${ARCH}"

python3 -m pip install -r requirements-dev.txt
VERIFY_FFMPEG="${1:-$(command -v ffmpeg)}"

python3 scripts/run_tests.py --report-dir artifacts/build-tests
python3 scripts/collect_notices.py
python3 -m PyInstaller packaging/transcodia.spec --noconfirm --clean

case "$(uname -s)" in
  Darwin)
    test -d dist/Transcodia.app
    python3 scripts/verify_bundle.py dist/Transcodia.app/Contents/MacOS/Transcodia --ffmpeg "$VERIFY_FFMPEG"
    ditto -c -k --keepParent dist/Transcodia.app "dist/Transcodia-${VERSION}-macos-${ARCH}.zip"
    echo "Built dist/Transcodia-${VERSION}-macos-${ARCH}.zip"
    ;;
  *)
    test -x dist/Transcodia/Transcodia
    python3 scripts/verify_bundle.py dist/Transcodia/Transcodia --ffmpeg "$VERIFY_FFMPEG"
    tar -C dist -czf "dist/Transcodia-${VERSION}-linux-${ARCH}.tar.gz" Transcodia
    echo "Built dist/Transcodia-${VERSION}-linux-${ARCH}.tar.gz"
    ;;
esac
