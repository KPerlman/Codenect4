import threading
import cv2
import numpy as np
from connect4_vision import Connect4Tracker

class VisionThread:
    def __init__(self):
        self.tracker = Connect4Tracker()
        self.latest_board = np.zeros((6, 7), dtype=int)
        self.running = True
        self.thread = threading.Thread(target=self.update_loop)
        self.thread.start()

    def update_loop(self):
        cap = cv2.VideoCapture(0)
        if cap.isOpened():
            cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        while self.running:
            ret, frame = cap.read()
            if ret:
                self.tracker.process_frame(frame)
                self.latest_board = np.copy(self.tracker.board_state)
        cap.release()

    def get_state(self):
        return self.latest_board

    def stop(self):
        self.running = False
        self.thread.join()