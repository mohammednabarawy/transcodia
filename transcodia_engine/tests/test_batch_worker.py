import asyncio
import os
import shutil
import pytest
from transcodia_engine.runtime_paths import find_ffmpeg
from transcodia_engine import (
    BatchConversionWorker,
    FFMpegEngine,
    ConvertTaskItem,
    VideoConfig,
    AudioConfig,
    VideoCodec,
    TaskStatus,
)

FFMPEG_BIN = find_ffmpeg()


def test_batch_worker_with_real_ffmpeg(tmp_path):
    """Executes a real mini-conversion using the resolved FFmpeg."""
    if not (os.path.exists(FFMPEG_BIN) or shutil.which(FFMPEG_BIN)):
        pytest.skip("FFmpeg executable not found.")

    out_file1 = str(tmp_path / "test_out1.mp4")
    out_file2 = str(tmp_path / "test_out2.mp4")

    # Generate tiny 0.2s synthetic lavfi video inputs
    engine = FFMpegEngine(ffmpeg_path=FFMPEG_BIN)

    task1 = ConvertTaskItem(
        src_file="color=c=blue:s=160x120:d=0.2",
        dst_file=out_file1,
        video_config=VideoConfig(codec=VideoCodec.H264, preset="ultrafast", crf=28),
        audio_config=AudioConfig(disable_audio=True),
        custom_input_prefix="-f lavfi",
    )
    task2 = ConvertTaskItem(
        src_file="color=c=red:s=160x120:d=0.2",
        dst_file=out_file2,
        video_config=VideoConfig(codec=VideoCodec.H264, preset="ultrafast", crf=28),
        audio_config=AudioConfig(disable_audio=True),
        custom_input_prefix="-f lavfi",
    )

    started = []
    completed = []

    def on_start(t_id, t):
        started.append(t_id)

    def on_complete(t_id, res):
        completed.append(res)

    worker = BatchConversionWorker(
        engine=engine,
        max_concurrency=2,
        on_start=on_start,
        on_complete=on_complete,
    )

    t1_id = worker.add_task(task1, total_duration_seconds=0.2)
    t2_id = worker.add_task(task2, total_duration_seconds=0.2)

    async def run():
        return await worker.run_all()

    results = asyncio.run(run())

    assert len(results) == 2
    assert t1_id in results and t2_id in results
    assert results[t1_id].status == TaskStatus.COMPLETED
    assert results[t2_id].status == TaskStatus.COMPLETED
    assert os.path.exists(out_file1) and os.path.getsize(out_file1) > 0
    assert os.path.exists(out_file2) and os.path.getsize(out_file2) > 0
    assert len(started) == 2
    assert len(completed) == 2


def test_worker_cancellation():
    worker = BatchConversionWorker(max_concurrency=1)
    task = ConvertTaskItem(src_file="in.mp4", dst_file="out.mp4")
    t_id = worker.add_task(task)

    assert worker._statuses[t_id] == TaskStatus.PENDING
    cancelled = worker.cancel_task(t_id)
    assert cancelled is True
    assert worker._statuses[t_id] == TaskStatus.CANCELLED
