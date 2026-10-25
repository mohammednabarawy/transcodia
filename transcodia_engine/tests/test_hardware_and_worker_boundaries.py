import asyncio
import sys

import pytest

from transcodia_engine import FFMpegEngine, BatchConversionWorker, ConvertTaskItem, TaskStatus
from transcodia_engine.hardware_prober import HardwareProber
from transcodia_engine.models import HardwareAccel, VideoCodec


@pytest.mark.parametrize("codec,prefix", [(VideoCodec.H264, "h264"), (VideoCodec.HEVC, "hevc")])
@pytest.mark.parametrize("mode,suffix", [(HardwareAccel.NVENC, "nvenc"), (HardwareAccel.QSV, "qsv"), (HardwareAccel.AMF, "amf"), (HardwareAccel.MEDIA_FOUNDATION, "mf")])
def test_requested_hardware_maps_to_the_requested_encoder(codec, prefix, mode, suffix):
    assert FFMpegEngine().resolve_video_encoder(codec, mode) == f"{prefix}_{suffix}"


@pytest.mark.parametrize("mode,suffix", [(HardwareAccel.NVENC, "nvenc"), (HardwareAccel.QSV, "qsv"), (HardwareAccel.AMF, "amf"), (HardwareAccel.MEDIA_FOUNDATION, "mf")])
def test_hardware_prober_never_claims_untested_support(monkeypatch, mode, suffix):
    prober = HardwareProber()
    monkeypatch.setattr(prober, "probe_compiled_encoders", lambda: {f"h264_{suffix}", f"hevc_{suffix}"})
    monkeypatch.setattr(prober, "test_encoder", lambda encoder: False)
    assert prober.resolve_best_encoder(VideoCodec.H264, mode) == ("libx264", HardwareAccel.NONE)
    with pytest.raises(RuntimeError):
        prober.resolve_best_encoder(VideoCodec.H264, mode, allow_fallback=False)
    assert not prober.probe().supported_hardware_encoders


def test_prober_caches_and_can_explicitly_recheck(monkeypatch):
    prober = HardwareProber()
    calls = []
    monkeypatch.setattr(prober, "probe_compiled_encoders", lambda: {"h264_nvenc"})
    monkeypatch.setattr(prober, "test_encoder", lambda encoder: calls.append(encoder) or True)
    assert prober.probe().nvenc_h264
    assert prober.probe().nvenc_h264
    assert len(calls) == 1
    prober.probe(force_recheck=True)
    assert len(calls) == 2


@pytest.mark.parametrize("count", [0, -1])
def test_invalid_concurrency_is_rejected(count):
    with pytest.raises(ValueError):
        BatchConversionWorker(max_concurrency=count)


def test_duplicate_task_ids_cannot_replace_another_job():
    worker = BatchConversionWorker()
    worker.add_task(ConvertTaskItem("one", "one.mp4"), task_id="same")
    with pytest.raises(ValueError):
        worker.add_task(ConvertTaskItem("two", "two.mp4"), task_id="same")


def test_long_carriage_return_progress_stream_does_not_overflow(tmp_path):
    destination = str(tmp_path / "out.bin")
    class ProgressEngine:
        def build_cli_arguments(self, task):
            script = "import sys;from pathlib import Path;sys.stderr.write('frame=12 time=00:00:01.00 speed=1x\\r'*5000);Path(sys.argv[1]).write_bytes(b'output')"
            return [sys.executable, "-c", script, task.dst_file]
    progresses = []
    worker = BatchConversionWorker(ProgressEngine(), on_progress=lambda *args: progresses.append(args))
    tid = worker.add_task(ConvertTaskItem("source", destination), total_duration_seconds=2)
    result = asyncio.run(worker.run_all())[tid]
    assert result.status == TaskStatus.COMPLETED, result.error_message
    assert progresses and progresses[-1][1].progress_percent == 50
