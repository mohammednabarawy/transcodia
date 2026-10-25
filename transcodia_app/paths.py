"""Allocate output names without overwriting an input, existing result, or queued job."""
import os


def available_output(path, reserved=()):
    used = {os.path.normcase(os.path.abspath(p)) for p in reserved}
    base, extension = os.path.splitext(path)
    candidate = path
    number = 1
    while os.path.exists(candidate) or os.path.normcase(os.path.abspath(candidate)) in used:
        candidate = f"{base}_{number}{extension}"
        number += 1
    return candidate
