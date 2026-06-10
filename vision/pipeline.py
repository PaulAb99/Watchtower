import cv2
import config
import threading
import queue

from shared.event_client import CloudEventClient
from vision.unknown_event_tracker import UnknownEventTracker


class TrackRecognizePipeline:
    def __init__(self, camera, tracker, face_id, state, follow_controller, servo):
        self.camera = camera
        self.tracker = tracker
        self.face_id = face_id
        self.state = state
        self.follow_controller = follow_controller
        self.servo = servo

        self.cloud_client = CloudEventClient()
        self.unknown_event_tracker = UnknownEventTracker(self.cloud_client)

        self.latest_frame = None
        self.latest_frame_lock = threading.Lock()

        self.frame_skip_counter = 0
        self.frame_idx = 0

        self.names_by_track = {}
        self.ttl_by_track = {}
        self.max_cached_tracks = 50
        self.track_order = []

        self.lost_target_frames = 0
        self.max_lost_before_switch = 6
        self.max_center_step_px = 18

        self.prev_center = None
        self.alpha = 0.85

        self.recognition_queue = queue.Queue(maxsize=5)
        self.running = True

        self.recognition_thread = threading.Thread(
            target=self._recognition_worker,
            daemon=True,
        )
        self.recognition_thread.start()

    def set_latest_frame(self, frame):
        with self.latest_frame_lock:
            self.latest_frame = frame.copy()

    def get_latest_frame(self):
        with self.latest_frame_lock:
            if self.latest_frame is None:
                return None
            return self.latest_frame.copy()

    def _decay_cache(self):
        dead = []

        for tid in list(self.ttl_by_track.keys()):
            self.ttl_by_track[tid] -= 1

            if self.ttl_by_track[tid] <= 0:
                dead.append(tid)

        for tid in dead:
            self.ttl_by_track.pop(tid, None)
            self.names_by_track.pop(tid, None)

            if tid in self.track_order:
                self.track_order.remove(tid)

        if len(self.names_by_track) > self.max_cached_tracks:
            excess = len(self.names_by_track) - self.max_cached_tracks

            for _ in range(excess):
                if self.track_order:
                    oldest_tid = self.track_order.pop(0)
                    self.names_by_track.pop(oldest_tid, None)
                    self.ttl_by_track.pop(oldest_tid, None)

    @staticmethod
    def _safe_crop(frame, box):
        h, w = frame.shape[:2]

        x1, y1, x2, y2 = box

        x1 = max(0, min(w - 1, int(x1)))
        x2 = max(0, min(w, int(x2)))
        y1 = max(0, min(h - 1, int(y1)))
        y2 = max(0, min(h, int(y2)))

        if x2 <= x1 or y2 <= y1:
            return None

        return frame[y1:y2, x1:x2]

    @staticmethod
    def _upper_body_box(box):
        x1, y1, x2, y2 = box
        h = y2 - y1

        new_y2 = int(y1 + h * 0.45)

        return (x1, y1, x2, new_y2)

    def _recognition_worker(self):
        while self.running:
            try:
                tid, crop = self.recognition_queue.get(timeout=1)
            except queue.Empty:
                continue

            try:
                result = self.face_id._identify_single(crop)

                name = result["name"]
                score = result["score"]

                if tid not in self.names_by_track:
                    self.track_order.append(tid)

                self.names_by_track[tid] = name

                if name != "Unknown":
                    self.unknown_event_tracker.update_known_seen(name)

                    if score >= config.FACE_SIM_THRESHOLD_HIGH:
                        self.ttl_by_track[tid] = config.TRACK_NAME_TTL_FRAMES * 2

                    elif score >= config.FACE_SIM_THRESHOLD_LOW:
                        self.ttl_by_track[tid] = config.TRACK_NAME_TTL_FRAMES // 2

                    else:
                        self.ttl_by_track[tid] = config.TRACK_NAME_TTL_FRAMES

                else:
                    # Important:
                    # Keep Unknown visible long enough to accumulate the 20s event timer.
                    self.ttl_by_track[tid] = config.TRACK_NAME_TTL_FRAMES

            except Exception as exc:
                print(f"[RECOGNITION WORKER ERROR] {type(exc).__name__}: {exc}")

    def run(self):
        while True:
            frame = self.camera.read()

            if frame is None:
                continue

            self.frame_idx += 1

            key = cv2.waitKey(1) & 0xFF

            if key == 27:
                break

            self._handle_key(key)

            if self.state.mode == "manual":
                manual_frame = frame.copy()
                self.set_latest_frame(manual_frame)

                cv2.imshow(
                    "Multiple Obj Detection - Main Obj Tracking",
                    manual_frame,
                )

                continue

            self._decay_cache()

            dets = self.tracker.track(frame)

            main_target = None
            tracked = None

            if not config.PETS:
                person_dets = [d for d in dets if d["label"] == "person"]
            else:
                person_dets = dets

            if person_dets:
                if self.state.tracked_id is not None:
                    same_track = [
                        d for d in person_dets
                        if d.get("track_id") == self.state.tracked_id
                    ]

                    if same_track:
                        main_target = same_track[0]
                        tracked = main_target["track_id"]
                        self.lost_target_frames = 0

                    else:
                        self.lost_target_frames += 1

                        if self.lost_target_frames < self.max_lost_before_switch:
                            main_target = None
                            tracked = self.state.tracked_id

                        else:
                            main_target = max(
                                person_dets,
                                key=lambda d: (
                                    d["box"][2] - d["box"][0]
                                ) * (
                                    d["box"][3] - d["box"][1]
                                ),
                            )

                            tracked = main_target["track_id"]
                            self.prev_center = None
                            self.lost_target_frames = 0

                else:
                    main_target = max(
                        person_dets,
                        key=lambda d: (
                            d["box"][2] - d["box"][0]
                        ) * (
                            d["box"][3] - d["box"][1]
                        ),
                    )

                    tracked = main_target["track_id"]
                    self.prev_center = None
                    self.lost_target_frames = 0

            else:
                main_target = None
                tracked = None
                self.lost_target_frames += 1

            if main_target:
                x1, y1, x2, y2 = main_target["box"]

                box_h = y2 - y1
                cx = (x1 + x2) // 2

                upper_body_ratio = 0.30
                cy = int(y1 + box_h * upper_body_ratio)

                raw_center = (cx, cy)

                if self.prev_center is None:
                    smoothed = raw_center

                else:
                    smoothed = (
                        int(
                            self.alpha * self.prev_center[0]
                            + (1 - self.alpha) * raw_center[0]
                        ),
                        int(
                            self.alpha * self.prev_center[1]
                            + (1 - self.alpha) * raw_center[1]
                        ),
                    )

                    dx = smoothed[0] - self.prev_center[0]
                    dy = smoothed[1] - self.prev_center[1]

                    dx = max(
                        -self.max_center_step_px,
                        min(self.max_center_step_px, dx),
                    )

                    dy = max(
                        -self.max_center_step_px,
                        min(self.max_center_step_px, dy),
                    )

                    smoothed = (
                        self.prev_center[0] + dx,
                        self.prev_center[1] + dy,
                    )

                self.prev_center = smoothed
                self.state.target_x = smoothed[0]
                self.state.target_y = smoothed[1]
                self.state.tracked_id = tracked

            else:
                self.prev_center = None
                self.state.target_x = None
                self.state.target_y = None
                self.state.tracked_id = None

            do_face = self.frame_idx % config.FACE_SCAN_EVERY_N_FRAMES == 0

            if do_face:
                face_person_dets = [
                    d for d in dets
                    if d.get("conf", 0) >= config.FACE_MIN_PERSON_CONF
                ]

                face_person_dets.sort(
                    key=lambda d: (
                        d["box"][2] - d["box"][0]
                    ) * (
                        d["box"][3] - d["box"][1]
                    ),
                    reverse=True,
                )

                face_person_dets = face_person_dets[:config.FACE_PROCESS_TOP_N]

                crops_to_process = []
                indices_to_process = []

                for i, d in enumerate(face_person_dets):
                    tid = d["track_id"]

                    if tid < 0:
                        continue

                    ttl_remaining = self.ttl_by_track.get(tid, 0)
                    max_ttl = config.TRACK_NAME_TTL_FRAMES

                    if tid in self.names_by_track and ttl_remaining > max_ttl * 0.5:
                        continue

                    crop = self._safe_crop(frame, d["box"])

                    if crop is None:
                        continue

                    crops_to_process.append(crop)
                    indices_to_process.append(i)

                if crops_to_process:
                    for det_idx in indices_to_process:
                        d = face_person_dets[det_idx]
                        tid = d["track_id"]

                        upper_box = self._upper_body_box(d["box"])
                        crop = self._safe_crop(frame, upper_box)

                        if crop is None:
                            continue

                        try:
                            self.recognition_queue.put_nowait((tid, crop))
                        except queue.Full:
                            pass

            # --------------------------------------------------
            # Unknown event logging
            # --------------------------------------------------

            for d in person_dets:
                tid = d.get("track_id")
                box = d.get("box")
                conf = d.get("conf", None)

                if tid is None or tid < 0:
                    continue

                name = self.names_by_track.get(tid)

                if name == "Unknown":
                    self.unknown_event_tracker.update_unknown_candidate(
                        frame=frame,
                        track_id=tid,
                        box=box,
                        confidence=conf,
                    )

                elif name and name != "Unknown":
                    self.unknown_event_tracker.update_known_seen(name)

            self.unknown_event_tracker.cleanup()

            annotated = self.tracker.draw(
                frame,
                dets,
                tracked,
                self.names_by_track,
            )

            self.set_latest_frame(annotated)

            cv2.imshow(
                "Multiple Obj Detection - Main Obj Tracking",
                annotated,
            )

            counts = {}

            for d in dets:
                label = d["label"]
                counts[label] = counts.get(label, 0) + 1

            if self.frame_idx % 5 == 0:
                print(counts)

        self.running = False

        if self.recognition_thread.is_alive():
            self.recognition_thread.join(timeout=2)

        self.camera.release()
        cv2.destroyAllWindows()

    def _handle_key(self, key):
        if key == 255:
            return

        step = 2.0

        if key == ord("m"):
            self.state.mode = "manual"
            print("[MODE] manual")
            return

        if key == ord("f"):
            self.state.mode = "follow"
            print("[MODE] follow")
            return

        if key == ord("c"):
            self.servo.center()
            return

        if self.state.mode != "manual":
            return

        if key == ord("a"):
            self.servo.left(step)

        elif key == ord("d"):
            self.servo.right(step)

        elif key == ord("w"):
            self.servo.up(step)

        elif key == ord("s"):
            self.servo.down(step)