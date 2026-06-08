from gpiozero import Servo as gpiozeroServo
from time import sleep


class Servo:
    """Stable wrapper around gpiozero.Servo for MG90S servos."""

    def __init__(self, gpio_pin):
        self.servo = gpiozeroServo(
            gpio_pin,
            min_pulse_width=0.0005,
            max_pulse_width=0.0025,
            initial_value=None
        )

        self.angle = None

    def set_angle(self, angle, force=False):
        angle = max(0, min(180, float(angle)))

        # Ignore tiny physical changes
        if not force and self.angle is not None:
            if abs(angle - self.angle) < 0.5:
                return

        self.angle = angle

        value = (angle / 180.0) * 2.0 - 1.0
        self.servo.value = value

        # Give servo time to receive the pulse
        sleep(0.08)

        # Deactivate PWM after each move to reduce jitter
        self.servo.detach()

    def cleanup(self):
        self.servo.detach()
        self.servo.close()