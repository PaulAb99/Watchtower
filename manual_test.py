import sys
import termios
import tty
import time

from tracking.servo_controller import ServoController


def getch():
    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)

    try:
        tty.setraw(fd)
        ch = sys.stdin.read(1)
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)

    return ch


def main():
    servo = ServoController(pan_pin=23, tilt_pin=18)

    step = 2.0

    print("Manual servo terminal test")
    print("W/A/S/D = move")
    print("C = center")
    print("+/- = change step")
    print("Q = quit")
    print()

    try:
        while True:
            key = getch().lower()

            if key == "q":
                break

            elif key == "a":
                servo.move_left(step)
                print(f"left  | pan={servo.pan:.1f}, tilt={servo.tilt:.1f}")

            elif key == "d":
                servo.move_right(step)
                print(f"right | pan={servo.pan:.1f}, tilt={servo.tilt:.1f}")

            elif key == "w":
                servo.move_up(step)
                print(f"up    | pan={servo.pan:.1f}, tilt={servo.tilt:.1f}")

            elif key == "s":
                servo.move_down(step)
                print(f"down  | pan={servo.pan:.1f}, tilt={servo.tilt:.1f}")

            elif key == "c":
                servo.center(force=True)
                print(f"center | pan={servo.pan:.1f}, tilt={servo.tilt:.1f}")

            elif key == "+" or key == "=":
                step = min(10.0, step + 0.5)
                print(f"step={step}")

            elif key == "-" or key == "_":
                step = max(0.5, step - 0.5)
                print(f"step={step}")

            time.sleep(0.02)

    finally:
        servo.cleanup()


if __name__ == "__main__":
    main()