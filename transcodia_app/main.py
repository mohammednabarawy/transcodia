"""
Transcodia - desktop application entry point.
A desktop media conversion suite for video, audio, pictures and documents.

Command line:
  --version      print the application version and exit
  --smoke-test   build the main window headlessly, then exit 0 (used by CI on packaged builds)
"""

import sys
import os
import argparse

# Ensure package roots are on PYTHONPATH
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from PySide6 import QtCore, QtGui, QtWidgets
from transcodia_app.version import APP_NAME, APP_VERSION
from transcodia_app.views.main_window import MainWindow


def _say(message: str) -> None:
    # Windowed (no-console) builds have no stdout.
    if sys.stdout is not None:
        print(message, flush=True)


def smoke_test(app: QtWidgets.QApplication) -> int:
    """Create the real main window, let it settle, and verify it is populated."""
    window = MainWindow(probe_hardware=False)
    window.show()
    for _ in range(5):
        app.processEvents()
    categories = window.category_panel.toolbox.count()
    window.close()
    if categories != 6:
        _say(f"smoke-test FAILED: expected 6 categories, found {categories}")
        return 1
    _say(f"smoke-test ok (version {APP_VERSION}, {categories} categories)")
    return 0


def main():
    parser = argparse.ArgumentParser(description="Transcodia desktop converter")
    parser.add_argument("--version", action="store_true")
    parser.add_argument("--smoke-test", action="store_true")
    parser.add_argument("--verify-runtime", metavar="REPORT", help="Check conversion dependencies and write a JSON report")
    args, qt_args = parser.parse_known_args()
    if args.version:
        _say(APP_VERSION)
        return 0
    run_smoke_test = args.smoke_test or bool(args.verify_runtime)
    qt_args = [sys.argv[0], *qt_args]

    # Setup application properties
    app = QtWidgets.QApplication(qt_args)
    app.setApplicationName(APP_NAME)
    app.setApplicationDisplayName("")
    app.setOrganizationName(APP_NAME)

    # Set default modern font
    font = QtGui.QFont("Segoe UI", 10)
    app.setFont(font)

    if run_smoke_test:
        status = smoke_test(app)
        if status == 0 and args.verify_runtime:
            from transcodia_app.runtime_check import verify_runtime
            return verify_runtime(args.verify_runtime)
        return status

    # Initialize and show main window
    window = MainWindow()
    window.show()

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
