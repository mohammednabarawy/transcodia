"""
Asynchronous Batch Processing Worker and Conversion Queue.
Runs several conversion tasks with bounded concurrency.
"""

import asyncio
import os
import time
import uuid
import glob
import re
import tempfile
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Dict, List, Optional, Any

from .models import ConvertTaskItem
from .engine import FFMpegEngine


class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class TaskProgress:
    current_seconds: float = 0.0
    progress_percent: Optional[float] = None
    fps: Optional[float] = None
    speed: Optional[float] = None
    frame: Optional[int] = None
    bitrate: Optional[str] = None


@dataclass
class TaskResult:
    task_id: str
    task: ConvertTaskItem
    status: TaskStatus
    returncode: Optional[int] = None
    elapsed_seconds: float = 0.0
    output_file: Optional[str] = None
    output_size_bytes: Optional[int] = None
    error_message: Optional[str] = None


class BatchConversionWorker:
    """Manages concurrent execution of media conversion tasks with live progress callbacks."""

    def __init__(
        self,
        engine: Optional[FFMpegEngine] = None,
        max_concurrency: int = 2,
        on_progress: Optional[Callable[[str, TaskProgress], None]] = None,
        on_start: Optional[Callable[[str, ConvertTaskItem], None]] = None,
        on_complete: Optional[Callable[[str, TaskResult], None]] = None,
    ):
        self.engine = engine or FFMpegEngine()
        if max_concurrency < 1:
            raise ValueError("Concurrency must be at least one.")
        self.max_concurrency = max_concurrency
        self.on_progress = on_progress
        self.on_start = on_start
        self.on_complete = on_complete

        self._queue: List[str] = []
        self._tasks: Dict[str, ConvertTaskItem] = {}
        self._durations: Dict[str, Optional[float]] = {}
        self._statuses: Dict[str, TaskStatus] = {}
        self._results: Dict[str, TaskResult] = {}
        self._processes: Dict[str, asyncio.subprocess.Process] = {}
        self._cancelled_ids: set = set()
        self._paused = False

    def add_task(
        self,
        task: ConvertTaskItem,
        total_duration_seconds: Optional[float] = None,
        task_id: Optional[str] = None,
    ) -> str:
        """Adds a conversion task to the batch queue."""
        t_id = task_id or str(uuid.uuid4())[:8]
        if t_id in self._tasks:
            raise ValueError(f"Duplicate task ID: {t_id}")
        self._tasks[t_id] = task
        self._durations[t_id] = total_duration_seconds
        self._statuses[t_id] = TaskStatus.PENDING
        self._queue.append(t_id)
        return t_id

    def cancel_task(self, task_id: str) -> bool:
        """Cancels a queued or currently executing task."""
        if task_id not in self._tasks:
            return False
        self._cancelled_ids.add(task_id)
        proc = self._processes.get(task_id)
        if proc and proc.returncode is None:
            try:
                proc.kill()
            except ProcessLookupError:
                pass
        self._statuses[task_id] = TaskStatus.CANCELLED
        return True

    def cancel_all(self):
        """Cancels all queued and active tasks."""
        for t_id in list(self._tasks.keys()):
            self.cancel_task(t_id)

    def pause(self):
        """Suspends all active worker processes."""
        self._paused = True
        try:
            import psutil
            for proc in self._processes.values():
                if proc.returncode is None and proc.pid:
                    try:
                        psutil.Process(proc.pid).suspend()
                    except Exception:
                        pass
        except ImportError:
            pass

    def resume(self):
        """Resumes all suspended worker processes."""
        self._paused = False
        try:
            import psutil
            for proc in self._processes.values():
                if proc.returncode is None and proc.pid:
                    try:
                        psutil.Process(proc.pid).resume()
                    except Exception:
                        pass
        except ImportError:
            pass

    async def _execute_single_task(self, task_id: str, semaphore: asyncio.Semaphore) -> TaskResult:
        async with semaphore:
            if task_id in self._cancelled_ids:
                res = TaskResult(
                    task_id=task_id,
                    task=self._tasks[task_id],
                    status=TaskStatus.CANCELLED,
                    error_message="Task was cancelled before execution."
                )
                self._results[task_id] = res
                if self.on_complete:
                    self.on_complete(task_id, res)
                return res

            task = self._tasks[task_id]
            total_duration = self._durations[task_id]
            self._statuses[task_id] = TaskStatus.RUNNING

            if self.on_start:
                self.on_start(task_id, task)

            start_time = time.time()
            error_lines = deque(maxlen=80)
            proc = None
            analysis_dir = None

            try:
                cli_args = self.engine.build_cli_arguments(task)
                os.makedirs(os.path.dirname(os.path.abspath(task.dst_file)), exist_ok=True)
                video = task.video_config
                if video and (video.two_pass or video.anti_shake):
                    analysis_dir = tempfile.TemporaryDirectory(prefix="transcodia-analysis-")
                    if video.anti_shake:
                        if task.is_concat or task.is_mux:
                            raise ValueError("Stabilize individual clips before joining or muxing them.")
                        transforms = os.path.join(analysis_dir.name, "motion.trf").replace("\\", "/")
                        transforms = transforms.replace(":", "\\:")
                        detect = [self.engine.ffmpeg_path, "-y", "-i", task.src_file, "-an", "-vf", f"vidstabdetect=result='{transforms}'", "-f", "null", os.devnull]
                        await self._run_analysis(task_id, detect)
                        cli_args = [argument.replace("vidstabtransform=smoothing=10", f"vidstabtransform=smoothing=10:input='{transforms}'") for argument in cli_args]
                    if video.two_pass:
                        if video.codec.value not in ("h264", "mpeg4") or video.hw_accel.value != "none" or not video.bitrate_kbps:
                            raise ValueError("Two-pass encoding requires a video bitrate and software H.264 or MPEG-4.")
                        log = os.path.join(analysis_dir.name, "encoding")
                        first = cli_args[:-1] + ["-pass", "1", "-passlogfile", log, "-an", "-f", "null", os.devnull]
                        await self._run_analysis(task_id, first)
                        cli_args[-1:-1] = ["-pass", "2", "-passlogfile", log]
                while self._paused and task_id not in self._cancelled_ids:
                    await asyncio.sleep(0.05)
                if task_id in self._cancelled_ids:
                    raise RuntimeError("Task cancelled by user.")
                proc = await asyncio.create_subprocess_exec(
                    *cli_args,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                self._processes[task_id] = proc
                if self._paused:
                    self.pause()

                async def read_stderr(stream):
                    pending = b""
                    while True:
                        chunk = await stream.read(4096)
                        lines = re.split(rb"[\r\n]", pending + chunk)
                        pending = lines.pop() if chunk else b""
                        for raw_line in lines:
                            line = raw_line.decode("utf-8", errors="replace").strip()
                            if line:
                                error_lines.append(line)
                                p_info = FFMpegEngine.parse_progress(line, total_duration)
                                if p_info and self.on_progress:
                                    self.on_progress(task_id, TaskProgress(**p_info))
                        pending = pending[-8192:]
                        if not chunk:
                            break

                async def read_stdout(stream):
                    while True:
                        line = await stream.readline()
                        if not line:
                            break

                await asyncio.gather(
                    read_stderr(proc.stderr),
                    read_stdout(proc.stdout),
                    proc.wait(),
                )

                elapsed = time.time() - start_time
                rc = proc.returncode

                if task_id in self._cancelled_ids:
                    status = TaskStatus.CANCELLED
                    err_msg = "Task cancelled by user."
                elif rc == 0:
                    status = TaskStatus.COMPLETED
                    err_msg = None
                else:
                    status = TaskStatus.FAILED
                    err_msg = "\n".join(error_lines) if error_lines else f"FFmpeg exited with error code {rc}"

                out_size = None
                if status == TaskStatus.COMPLETED:
                    if os.path.exists(task.dst_file):
                        out_size = os.path.getsize(task.dst_file)
                    elif re.search(r"%0?\d*d", task.dst_file):
                        pattern = re.sub(r"%0?\d*d", "*", glob.escape(task.dst_file))
                        out_size = sum(os.path.getsize(path) for path in glob.glob(pattern) if os.path.isfile(path))
                    if not out_size:
                        status = TaskStatus.FAILED
                        err_msg = "FFmpeg exited without producing a non-empty output."

                result = TaskResult(
                    task_id=task_id,
                    task=task,
                    status=status,
                    returncode=rc,
                    elapsed_seconds=elapsed,
                    output_file=task.dst_file if status == TaskStatus.COMPLETED else None,
                    output_size_bytes=out_size,
                    error_message=err_msg,
                )

            except Exception as ex:
                elapsed = time.time() - start_time
                status = TaskStatus.FAILED if task_id not in self._cancelled_ids else TaskStatus.CANCELLED
                result = TaskResult(
                    task_id=task_id,
                    task=task,
                    status=status,
                    elapsed_seconds=elapsed,
                    error_message=f"{type(ex).__name__}: {ex}",
                )
            finally:
                if proc and proc.returncode is None:
                    proc.kill()
                    await proc.wait()
                self._processes.pop(task_id, None)
                if analysis_dir:
                    analysis_dir.cleanup()

            self._statuses[task_id] = result.status
            self._results[task_id] = result

            if self.on_complete:
                self.on_complete(task_id, result)

            return result

    async def _run_analysis(self, task_id, command):
        while self._paused and task_id not in self._cancelled_ids:
            await asyncio.sleep(0.05)
        if task_id in self._cancelled_ids:
            raise RuntimeError("Task cancelled by user.")
        process = await asyncio.create_subprocess_exec(*command, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        self._processes[task_id] = process
        if self._paused:
            self.pause()
        try:
            _, stderr = await process.communicate()
            if process.returncode:
                raise RuntimeError(stderr.decode("utf-8", errors="replace")[-4000:])
        finally:
            if process.returncode is None:
                process.kill()
                await process.wait()
            self._processes.pop(task_id, None)

    async def run_all(self) -> Dict[str, TaskResult]:
        """Runs all queued tasks up to the concurrency limit."""
        semaphore = asyncio.Semaphore(self.max_concurrency)
        tasks_to_run = [self._execute_single_task(t_id, semaphore) for t_id in self._queue]
        await asyncio.gather(*tasks_to_run)
        return self._results

    def get_result(self, task_id: str) -> Optional[TaskResult]:
        """Returns the result of an executed task."""
        return self._results.get(task_id)
