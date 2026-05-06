import cv2
import numpy as np
cap = cv2.VideoCapture('/tmp/pytest-of-potato/pytest-7/test_pipeline_e2e0/output.mp4')
cap.set(cv2.CAP_PROP_POS_FRAMES, 150)
ret, frame = cap.read()
if ret:
    print("Pixel at 250, 300:", frame[250, 300])
    print("Pixel at 10, 10:", frame[10, 10])
