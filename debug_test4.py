import cv2
import numpy as np

cap = cv2.VideoCapture('/tmp/debug_out.mp4')
cap.set(cv2.CAP_PROP_POS_FRAMES, 150)
ret, frame = cap.read()
if ret:
    mask = np.all(frame == [0, 0, 0], axis=-1)
    coords = np.argwhere(mask)
    if len(coords) > 0:
        print("Min y,x:", coords.min(axis=0))
        print("Max y,x:", coords.max(axis=0))
    else:
        print("No pure black pixels found.")
