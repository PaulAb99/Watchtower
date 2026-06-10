import time
import threading
from gpiozero import Servo as GpioServo


class SimpleAxis:
    def __init__(
        self,
        name,
        pin,
        center,
        min_angle,
        max_angle,
        inverted=False,
        pulse_time=0.18,
    ):
        self.name = name
        self.servo = GpioServo(
            pin,
            min_pulse_width=0.0005,
            max_pulse_width=0.0025,
            initial_value=None,
        )

        self.angle = float(center)
        self.center_angle = float(center)
        self.min_angle = float(min_angle)
        self.max_angle = float(max_angle)
        self.inverted = inverted
        self.pulse_time = pulse_time

        self.lock = threading.Lock()

        self.goto(self.angle)

    def _clamp(self, angle):
        return max(self.min_angle, min(self.max_angle, float(angle)))

    def _write(self, angle):
        value = (angle / 180.0) * 2.0 - 1.0
        self.servo.value = value
        time.sleep(self.pulse_time)
        self.servo.detach()

    def goto(self, angle):
        with self.lock:
            old = self.angle
            new = self._clamp(angle)

            self.angle = new

            print(f"[SERVO {self.name}] {old:.1f} -> {new:.1f}")

            self._write(new)

    def nudge(self, direction, step):
        if self.inverted:
            direction *= -1

        self.goto(self.angle + direction * step)

    def center(self):
        self.goto(self.center_angle)

    def cleanup(self):
        self.servo.detach()
        self.servo.close()


class SimplePanTilt:
    def __init__(self, pan_pin=23, tilt_pin=18):
        self.pan = SimpleAxis(
            name="PAN",
            pin=pan_pin,
            center=90,
            min_angle=15,
            max_angle=165,
            inverted=True,
        )

        self.tilt = SimpleAxis(
            name="TILT",
            pin=tilt_pin,
            center=30,
            min_angle=15,
            max_angle=65,
            inverted=False,
        )

    def left(self, step=2.0):
        self.pan.nudge(-1, step)

    def right(self, step=2.0):
        self.pan.nudge(1, step)

    def up(self, step=2.0):
        self.tilt.nudge(-1, step)

    def down(self, step=2.0):
        self.tilt.nudge(1, step)

    def center(self):
        self.pan.center()
        self.tilt.center()

    def cleanup(self):
        self.center()
        time.sleep(0.3)
        self.pan.cleanup()
        self.tilt.cleanup()