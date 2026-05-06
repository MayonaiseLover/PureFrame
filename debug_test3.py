import cv2
import numpy as np

cap = cv2.VideoCapture('/tmp/debug_out.mp4')
cap.set(cv2.CAP_PROP_POS_FRAMES, 150)
ret, frame = cap.read()
if ret:
    print(np.unique(frame.reshape(-1, 3), axis=0))
