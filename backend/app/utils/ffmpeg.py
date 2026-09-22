"""ffmpeg/ffprobe 子进程共享执行器（kb 转写/视觉与社媒转写共用）。

只负责进程往返与可执行文件缺失归类（FFmpegError）；返回码非零不是异常
（由调用方按各自语义处理），stderr 的领域解析（silencedetect/showinfo）
在 transcribe_pipeline / vision_pipeline 纯函数中完成。
"""

import asyncio
from typing import Literal, overload


class FFmpegError(RuntimeError):
    """ffmpeg/ffprobe 可执行文件缺失。"""


@overload
async def run(*args: str, capture_stdout: Literal[True]) -> tuple[int, str, bytes]: ...


@overload
async def run(*args: str, capture_stdout: Literal[False] = ...) -> tuple[int, str]: ...


async def run(
    *args: str, capture_stdout: bool = False
) -> tuple[int, str] | tuple[int, str, bytes]:
    """执行 ffmpeg/ffprobe 子进程，返回 (returncode, stderr[, stdout])。

    Raises:
        FFmpegError: 可执行文件缺失。
    """
    try:
        proc = await asyncio.create_subprocess_exec(
            *args,
            stdout=asyncio.subprocess.PIPE if capture_stdout else asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
    except FileNotFoundError as exc:
        raise FFmpegError("ffmpeg_unavailable") from exc
    err = stderr.decode(errors="replace")
    if capture_stdout:
        return proc.returncode or 0, err, stdout
    return proc.returncode or 0, err
