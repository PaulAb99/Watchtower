import time
from tracking.servo import Servo


class ServoController:

    def __init__(self, pan_pin=23, tilt_pin=18):
        self.pan_servo = Servo(pan_pin)
        self.tilt_servo = Servo(tilt_pin)

        self.pan_center = 90.0
        self.tilt_center = 20.0

        self.pan = self.pan_center
        self.tilt = self.tilt_center

        self.pan_min = 20
        self.pan_max = 160

        self.tilt_min = 20
        self.tilt_max = 60

        self.min_interval = 0.15
        self.max_step = 0.35
        self.min_angle_change = 0.15

        self.last_update_pan = 0
        self.last_update_tilt = 0

        self.frozen = False

        self.center(force=True)

    def _move_towards(self, current, target):
        delta = target - current

        if abs(delta) < self.min_angle_change:
            return current

        if delta > self.max_step:
            return current + self.max_step

        if delta < -self.max_step:
            return current - self.max_step

        return target

    def set_pan(self, target_angle, force=False):
        if self.frozen and not force:
            return

        now = time.time()
        if not force and now - self.last_update_pan < self.min_interval:
            return

        target_angle = max(self.pan_min, min(self.pan_max, float(target_angle)))

        if force:
            self.pan = target_angle
            self.pan_servo.set_angle(self.pan, force=True)
            self.last_update_pan = now
            return

        new_pan = self._move_towards(self.pan, target_angle)

        if abs(new_pan - self.pan) >= self.min_angle_change:
            self.pan = new_pan
            self.last_update_pan = now
            self.pan_servo.set_angle(self.pan)

    def set_tilt(self, target_angle, force=False):
        if self.frozen and not force:
            return

        now = time.time()
        if not force and now - self.last_update_tilt < self.min_interval:
            return

        target_angle = max(self.tilt_min, min(self.tilt_max, float(target_angle)))

        if force:
            self.tilt = target_angle
            self.tilt_servo.set_angle(self.tilt, force=True)
            self.last_update_tilt = now
            return

        new_tilt = self._move_towards(self.tilt, target_angle)

        if abs(new_tilt - self.tilt) >= self.min_angle_change:
            self.tilt = new_tilt
            self.last_update_tilt = now
            self.tilt_servo.set_angle(self.tilt)

    def freeze(self):
        self.frozen = True

    def unfreeze(self):
        self.frozen = False

    def center(self, force=False):
        self.set_pan(self.pan_center, force=force)
        self.set_tilt(self.tilt_center, force=force)

    def cleanup(self):
        self.center(force=True)
        time.sleep(0.5)

        self.pan_servo.cleanup()
        self.tilt_servo.cleanup()