import asyncio
import subprocess
import sys
from dataclasses import asdict

import pytest

from transcodia_engine import BatchConversionWorker, ConvertTaskItem, FFMpegEngine, TaskStatus
from transcodia_engine.models import AudioConfig, HardwareAccel, MediaAdditionalConfig, VideoCodec, VideoConfig


class UnavailableHardwareEngine(FFMpegEngine):
    def __init__(self, ffmpeg):
        super().__init__(ffmpeg)
        self.attempts = []

    def build_cli_arguments(self, task):
        self.attempts.append(task)
        if task.video_config.hw_accel != HardwareAccel.NONE:
            script = "import sys;sys.stderr.write('CUDA_ERROR_NO_DEVICE: no CUDA capable device\\n');sys.exit(1)"
            return [sys.executable, "-c", script]
        return super().build_cli_arguments(task)


@pytest.mark.parametrize("codec", [VideoCodec.H264, VideoCodec.HEVC])
@pytest.mark.parametrize("hardware", [HardwareAccel.NVENC, HardwareAccel.QSV, HardwareAccel.AMF, HardwareAccel.MEDIA_FOUNDATION])
def test_unavailable_hardware_retries_once_and_decodes_real_output(ffmpeg_bin, media_files, tmp_path, codec, hardware):
    engine = UnavailableHardwareEngine(ffmpeg_bin)
    task = ConvertTaskItem(media_files["video"], str(tmp_path / "fallback.mp4"),
        video_config=VideoConfig(codec=codec, hw_accel=hardware, preset="p4", cq=25, width=80, height=60),
        audio_config=AudioConfig(), additional_config=MediaAdditionalConfig(end_time=1))
    before = asdict(task)
    started, completed = [], []
    worker = BatchConversionWorker(engine, max_concurrency=1, on_start=lambda *args: started.append(args),
                                    on_complete=lambda *args: completed.append(args))
    tid = worker.add_task(task)
    result = asyncio.run(worker.run_all())[tid]
    assert result.status == TaskStatus.COMPLETED, result.error_message
    assert result.error_message is None and "software encoding" in result.warning_message
    assert len(engine.attempts) == 2 and len(started) == len(completed) == 1
    assert result.task is task and asdict(task) == before
    fallback = engine.attempts[1]
    assert fallback.video_config.hw_accel == HardwareAccel.NONE
    assert fallback.video_config.preset == "fast" and fallback.video_config.crf == 25
    assert fallback.additional_config == task.additional_config and fallback.audio_config == task.audio_config
    decoded = subprocess.run([ffmpeg_bin, "-v", "error", "-i", task.dst_file, "-frames:v", "1",
                              "-f", "rawvideo", "-pix_fmt", "rgb24", "pipe:1"], capture_output=True, timeout=15, check=True)
    assert len(decoded.stdout) == 80 * 60 * 3


def test_both_encoder_failures_keep_diagnostics_without_a_retry_loop(ffmpeg_bin, tmp_path):
    engine = UnavailableHardwareEngine(ffmpeg_bin)
    task = ConvertTaskItem(str(tmp_path / "missing.mp4"), str(tmp_path / "out.mp4"),
                           video_config=VideoConfig(hw_accel=HardwareAccel.NVENC))
    completed = []
    worker = BatchConversionWorker(engine, on_complete=lambda *args: completed.append(args))
    tid = worker.add_task(task)
    result = asyncio.run(worker.run_all())[tid]
    assert result.status == TaskStatus.FAILED
    assert "CUDA_ERROR_NO_DEVICE" in result.error_message and "Software encoding also failed" in result.error_message
    assert len(engine.attempts) == 2 and len(completed) == 1


def test_cancelling_hardware_attempt_does_not_start_software(ffmpeg_bin, tmp_path):
    class SlowHardware(UnavailableHardwareEngine):
        def build_cli_arguments(self, task):
            self.attempts.append(task)
            script = "import sys,time;sys.stderr.write('frame=1 time=00:00:00.10 speed=1x\\r');sys.stderr.flush();time.sleep(5)"
            return [sys.executable, "-c", script]
    engine = SlowHardware(ffmpeg_bin)
    worker = BatchConversionWorker(engine, on_progress=lambda tid, progress: worker.cancel_task(tid))
    tid = worker.add_task(ConvertTaskItem("source", str(tmp_path / "cancelled.mp4"),
                                         video_config=VideoConfig(hw_accel=HardwareAccel.NVENC)))
    result = asyncio.run(worker.run_all())[tid]
    assert result.status == TaskStatus.CANCELLED and len(engine.attempts) == 1
