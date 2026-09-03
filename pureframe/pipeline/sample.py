from pathlib import Path
import numpy as np
import ffmpeg
from .shots import Shot
from pureframe.utils.ffmpeg import extract_metadata, probe


def sample_keyframes(shot: Shot, n: int) -> list[int]:
    length = shot.end_frame - shot.start_frame
    if length <= n:
        return list(range(shot.start_frame, shot.end_frame))

    # Evenly spaced
    # If n=3: start, mid, end-1
    indices = np.linspace(shot.start_frame, shot.end_frame - 1, n, dtype=int)
    return sorted(list(set(indices)))


def extract_frames(
    path: Path, frame_indices: list[int], downscale_max_edge: int
) -> dict[int, np.ndarray]:
    if not frame_indices:
        return {}

    meta = extract_metadata(probe(path))

    # Calculate scale
    w, h = meta.width, meta.height
    if w > h and w > downscale_max_edge:
        h = int(h * (downscale_max_edge / w))
        w = downscale_max_edge
    elif h > w and h > downscale_max_edge:
        w = int(w * (downscale_max_edge / h))
        h = downscale_max_edge
    w = w - (w % 2)
    h = h - (h % 2)

    # Build select filter string
    # select='eq(n,0)+eq(n,10)+...'
    select_expr = "+".join([f"eq(n,{i})" for i in frame_indices])

    process = (
        ffmpeg.input(str(path))
        .filter("select", select_expr)
        .filter("scale", w, h)
        .output("pipe:", format="rawvideo", pix_fmt="bgr24", vsync=0)
        .run_async(pipe_stdout=True, pipe_stderr=True)
    )

    # Drain stderr in a background thread. Long `select` expressions make
    # ffmpeg emit per-frame warnings; if nobody reads stderr, the OS pipe
    # buffer fills up, ffmpeg blocks, and our stdout read deadlocks.
    import threading

    def _drain(pipe):
        try:
            while pipe.read(65536):
                pass
        except Exception:
            pass

    drain_t = threading.Thread(target=_drain, args=(process.stderr,), daemon=True)
    drain_t.start()

    frame_size = w * h * 3
    results = {}

    try:
        for idx in frame_indices:
            in_bytes = process.stdout.read(frame_size)
            if not in_bytes or len(in_bytes) != frame_size:
                break
            frame = np.frombuffer(in_bytes, np.uint8).reshape([h, w, 3])
            results[idx] = frame
    finally:
        process.stdout.close()
        process.wait()
        drain_t.join(timeout=2.0)

    return results
