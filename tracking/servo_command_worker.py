import queue
import threading
import time


class ServoCommandWorker:
    def __init__(self, servo):
        self.servo = servo
        self.commands = queue.Queue(maxsize=1)
        self.running = True

        self.max_pan_command_step = 0.15
        self.max_tilt_command_step = 0.15

        self.thread = threading.Thread(target=self.loop, daemon=True)
        self.thread.start()

    def send(self, command, value=None):
        print(f"[SERVO WORKER SEND] command={command}, value={value}")
        if command in ("pan_to", "tilt_to", "left", "right", "up", "down"):
            while not self.commands.empty():
                try:
                    self.commands.get_nowait()
                except queue.Empty:
                    break

        if self.commands.full():
            try:
                self.commands.get_nowait()
            except queue.Empty:
                pass

        self.commands.put((command, value))

    def _clamp_relative(self, current, target, max_step):
        if target is None:
            return current

        target = float(target)
        delta = target - current

        if delta > max_step:
            return current + max_step

        if delta < -max_step:
            return current - max_step

        return target

    def loop(self):
        while self.running:
            try:
                command, value = self.commands.get(timeout=0.1)
            except queue.Empty:
                continue

            if command == "left":
                self.servo.move_left(value or 2.0)

            elif command == "right":
                self.servo.move_right(value or 2.0)

            elif command == "up":
                self.servo.move_up(value or 2.0)

            elif command == "down":
                self.servo.move_down(value or 2.0)

            elif command == "center":
                self.servo.center(force=True)

            elif command == "freeze":
                self.servo.freeze()

            elif command == "unfreeze":
                self.servo.unfreeze()

            elif command == "move_to":
                pan_target, tilt_target = value

                safe_pan = self._clamp_relative(
                    self.servo.pan,
                    pan_target,
                    self.max_pan_command_step
                )

                safe_tilt = self._clamp_relative(
                self.servo.tilt,
                tilt_target,
                self.max_tilt_command_step
                )

                self.servo.set_pan(safe_pan)
                self.servo.set_tilt(safe_tilt)

            time.sleep(0.01)

    def stop(self):
        self.running = False
        if self.thread.is_alive():
            self.thread.join(timeout=2)