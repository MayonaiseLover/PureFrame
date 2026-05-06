import pytest
from pathlib import Path
import subprocess
import cv2
import numpy as np

from pureframe.cli import process
from pureframe.hardware import HardwareProfile
from pureframe.pipeline.detect.nudity import NudityDetector, Detection
import pureframe.cli

def test():
    synthetic_video = Path('/home/potato/Downloads/githup/PureFrame(antigravity)/tests/fixtures/synthetic_explicit.mp4')
    out_path = Path('/tmp/debug_out.mp4')

    original_get_settings = pureframe.cli.get_settings
    def mocked_get_settings(profile):
        s = original_get_settings(profile)
        s.sample_keyframes_per_shot = 10
        return s
    pureframe.cli.get_settings = mocked_get_settings

    def mocked_detect_batch(self, frames_bgr):
        batch_res = []
        for frame in frames_bgr:
            h, w = frame.shape[:2]
            px_x = int(300 * w / 1280)
            px_y = int(250 * h / 720)
            pixel = frame[px_y, px_x]
            if not np.allclose(pixel, [128, 128, 128], atol=20):
                batch_res.append([Detection(label="FEMALE_BREAST_EXPOSED", score=0.99, box=(50, 40, 100, 85))])
            else:
                batch_res.append([])
        return batch_res

    NudityDetector.detect_batch = mocked_detect_batch

    process(input=synthetic_video, output=out_path, profile=HardwareProfile.CPU, threshold=0.5)

if __name__ == "__main__":
    test()
