import asyncio
import sys
from pathlib import Path

import pytest

from transcodia_engine import BatchConversionWorker, FFMpegEngine, ConvertTaskItem, TaskStatus


def test_failed_job_does_not_block_next_job(ffmpeg_bin, media_files, tmp_path):
    complete = []
    worker = BatchConversionWorker(FFMpegEngine(ffmpeg_bin), max_concurrency=1, on_complete=lambda tid, result: complete.append((tid, result.status)))
    bad = worker.add_task(ConvertTaskItem(str(tmp_path / "missing.mp4"), str(tmp_path / "bad.mp4")))
    good = worker.add_task(ConvertTaskItem(media_files["video"], str(tmp_path / "good.mp4")))
    results = asyncio.run(worker.run_all())
    assert results[bad].status == TaskStatus.FAILED
    assert results[bad].error_message
    assert results[good].status == TaskStatus.COMPLETED
    assert len(complete) == 2


def test_precancelled_job_reports_completion_callback(tmp_path):
    callbacks = []
    worker = BatchConversionWorker(on_complete=lambda *args: callbacks.append(args))
    tid = worker.add_task(ConvertTaskItem("unused", str(tmp_path / "never.mp4")))
    assert worker.cancel_task(tid)
    result = asyncio.run(worker.run_all())[tid]
    assert result.status == TaskStatus.CANCELLED
    assert len(callbacks) == 1
    assert not (tmp_path / "never.mp4").exists()


def test_missing_executable_is_a_failed_task_not_a_batch_crash(tmp_path):
    worker = BatchConversionWorker(FFMpegEngine(str(tmp_path / "missing-ffmpeg.exe")))
    tid = worker.add_task(ConvertTaskItem("source", str(tmp_path / "out.mp4")))
    result = asyncio.run(worker.run_all())[tid]
    assert result.status == TaskStatus.FAILED
    assert result.error_message


def test_zero_exit_without_an_output_is_not_success(tmp_path):
    class NoOutputEngine:
        def build_cli_arguments(self, task):
            return [sys.executable, "-c", "pass"]
    worker = BatchConversionWorker(NoOutputEngine())
    tid = worker.add_task(ConvertTaskItem("source", str(tmp_path / "missing.mp4")))
    result = asyncio.run(worker.run_all())[tid]
    assert result.status == TaskStatus.FAILED


def test_invalid_command_configuration_is_isolated(tmp_path):
    class BrokenEngine:
        def build_cli_arguments(self, task):
            raise ValueError("invalid configuration")
    worker = BatchConversionWorker(BrokenEngine())
    tid = worker.add_task(ConvertTaskItem("source", str(tmp_path / "out.mp4")))
    result = asyncio.run(worker.run_all())[tid]
    assert result.status == TaskStatus.FAILED
    assert "invalid configuration" in result.error_message


def test_pause_resume_and_cancel_running_and_waiting_jobs(ffmpeg_bin, media_files, tmp_path):
    import psutil
    callbacks = []
    worker = BatchConversionWorker(FFMpegEngine(ffmpeg_bin), max_concurrency=1,
        on_complete=lambda tid, result: callbacks.append(tid))
    first = worker.add_task(ConvertTaskItem(media_files["video"], str(tmp_path / "first.mp4"), custom_input_prefix="-re"))
    second = worker.add_task(ConvertTaskItem(media_files["video"], str(tmp_path / "second.mp4")))
    async def exercise():
        pending = asyncio.create_task(worker.run_all())
        async def wait_for_process():
            while first not in worker._processes:
                await asyncio.sleep(0.01)
        await asyncio.wait_for(wait_for_process(), 5)
        process = worker._processes[first]
        worker.pause()
        assert psutil.Process(process.pid).status() == psutil.STATUS_STOPPED
        assert second not in worker._processes
        worker.resume()
        worker.cancel_all()
        return await asyncio.wait_for(pending, 8)
    results = asyncio.run(exercise())
    assert all(r.status == TaskStatus.CANCELLED for r in results.values())
    assert set(callbacks) == {first, second}
    assert not (tmp_path / "second.mp4").exists()
