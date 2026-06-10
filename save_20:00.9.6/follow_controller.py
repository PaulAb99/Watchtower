import time
import threading


class FollowController:

    def __init__(self, state, servo):
        self.state = state
        self.servo = servo

        # Larger deadzone because camera + detection are noisy
        self.deadzone_x = 80
        self.deadzone_y = 80

        # P gains
        self.pan_gain = 0.0015
        self.tilt_gain = 0.001

        # D gains: damp sudden changes
        self.pan_d_gain = 0.0
        self.tilt_d_gain = 0.0

        # Limit correction
        self.max_correction = 0.30

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
            time.sleep(0.05)

    def update(self):
        if self.state.mode != "follow":
            return

        has_target = (
            self.state.target_x is not None and
            self.state.target_y is not None
        )

        if has_target:
            self.detection_counter += 1
            self.lost_counter = 0

            if not self.tracking:
                if self.detection_counter >= self.target_confirmation_frames:
                    self.tracking = True
                    self.servo.unfreeze()
                    print("[TRACKING START] Target confirmed")

        else:
            self.detection_counter = 0
            self.lost_counter += 1

            # Do not stop instantly on bad camera frames
            if self.lost_counter >= self.lost_frame_limit:
                if self.tracking:
                    print("[TRACKING STOP] Target lost")

                self.tracking = False
                self.servo.freeze()

            return

        if not self.tracking:
            return

        frame_cx = self.state.frame_width // 2
        frame_cy = self.state.frame_height // 2

        error_x = self.state.target_x - frame_cx
        error_y = self.state.target_y - frame_cy

        # Clamp extreme errors from bad detections
        error_x = max(-160, min(160, error_x))
        error_y = max(-120, min(120, error_y))

        # Deadzone around center
        if abs(error_x) < self.deadzone_x:
            error_x = 0

        if abs(error_y) < self.deadzone_y:
            error_y = 0

        # Error derivative
        d_error_x = error_x - self.prev_error_x
        d_error_y = error_y - self.prev_error_y

        # PAN
        if error_x != 0:
            pan_correction = (
                error_x * self.pan_gain +
                d_error_x * self.pan_d_gain
            )

            pan_correction = max(
                -self.max_correction,
                min(self.max_correction, pan_correction)
            )

            target_pan = self.servo.pan + pan_correction
            self.servo.set_pan(target_pan)

        # TILT
        if error_y != 0:
            tilt_correction = (
                error_y * self.tilt_gain +
                d_error_y * self.tilt_d_gain
            )

            tilt_correction = max(
                -self.max_correction,
                min(self.max_correction, tilt_correction)
            )

            target_tilt = self.servo.tilt - tilt_correction
            self.servo.set_tilt(target_tilt)

        self.prev_error_x = error_x
        self.prev_error_y = error_y

    def stop(self):
        self.running = False