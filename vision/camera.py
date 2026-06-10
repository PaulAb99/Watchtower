import cv2
import config
import platform
import threading
import queue


class Camera:
    def __init__(self, index=None, width=None, height=None, fps=None):
        self.platform = platform.system()
        self.is_rpi = self._detect_rpi()

        if index is None:
            index = self._find_camera()

        if index is None:
            raise RuntimeError("No camera found")

        self.cap = cv2.VideoCapture(index)
        if not self.cap.isOpened():
            raise RuntimeError(f"Could not open camera at index {index}")

        width = width or config.CAMERA_WIDTH
        height = height or config.CAMERA_HEIGHT
        fps = fps or config.CAMERA_FPS

        self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
        self.cap.set(cv2.CAP_PROP_FPS, fps)

        if self.is_rpi:
            self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

        self.frame_skip = config.CAMERA_FRAME_SKIP

        # thread upgrade

        self.frame_queue = queue.Queue(maxsize=1)
        self.running = True

        self.capture_thread = threading.Thread(
            target=self._capture_loop,
            daemon=True
        )
        self.capture_thread.start()

    def _detect_rpi(self):
        try:
            with open('/proc/cpuinfo', 'r') as f:
                return 'Raspberry Pi' in f.read() or 'BCM' in f.read()
        except:
            return False

    def _find_camera(self):
        print(f"Scanning for cameras on {self.platform}...")
        for i in range(5):
            cap = cv2.VideoCapture(i)
            if cap.isOpened():
                cap.release()
                print(f"Found camera at index {i}")
                return i
        return None

    def read(self):
        try:
            return self.frame_queue.get(timeout=1)
        except queue.Empty:
            return None

    def read_skip(self):
        return self.read()

    def release(self):
        self.running = False

        if self.capture_thread.is_alive():
            self.capture_thread.join(timeout=1)

        self.cap.release()

        

    def _capture_loop(self):
        while self.running:
            ret, frame = self.cap.read()

            if not ret:
                continue

            if self.frame_queue.full():
                try:
                    self.frame_queue.get_nowait()
                except queue.Empty:
                    pass

            self.frame_queue.put(frame)
