import time
import threading

from tracking import servo


class FollowController:

    def __init__(self, state, servo_command):
        self.state = state
        self.servo_command = servo_command

        # Larger deadzone because camera + detection are noisy
        self.deadzone_x = 80
        self.deadzone_y = 80

        # P gains
        self.pan_gain = 0.20
        self.tilt_gain = 0.15

        # D gains: damp sudden changes
        self.pan_d_gain = 0.0
        self.tilt_d_gain = 0.0


        # Detection stability
        self.target_confirmation_frames = 3
        self.lost_frame_limit = 12

        self.detection_counter = 0
        self.lost_counter = 0
        self.tracking = False

        self.prev_error_x = 0
        self.prev_error_y = 0

        self.running = True

        print("[FOLLOW_CONTROLLER] Initialized")

        self.thread = threading.Thread(target=self.loop, daemon=True)
        self.thread.start()

    def loop(self):
        print("[FOLLOW_CONTROLLER] Loop thread started")

        while self.running:
            self.update()
            time.sleep(0.01)

    def update(self):
        if self.state.mode != "follow":
            return

        if self.state.target_x is None or self.state.target_y is None:
            return

        frame_cx = self.state.frame_width // 2
        frame_cy = self.state.frame_height // 2

        error_x = self.state.target_x - frame_cx
        error_y = self.state.target_y - frame_cy

        deadzone_x = 100
        deadzone_y = 100

        if error_x > deadzone_x:
            self.servo_command.right(1.0)
        elif error_x < -deadzone_x:
            self.servo_command.left(1.0)

        if error_y > deadzone_y:
            self.servo_command.down(0.7)
        elif error_y < -deadzone_y:
            self.servo_command.up(0.7)

    def stop(self):
        self.running = False