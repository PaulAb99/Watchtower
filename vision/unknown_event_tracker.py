import time
import config


class UnknownEventTracker:
    """
    Event gate for unknown-person logging.

    Rule:
    - Same track_id must stay Unknown for UNKNOWN_EVENT_MIN_SECONDS.
    - No known person must have been seen for KNOWN_PERSON_COOLDOWN_SECONDS.
    - Upload only one image per unknown track_id.
    """

    def __init__(self, cloud_client):
        self.cloud_client = cloud_client

        self.unknown_first_seen = {}
        self.unknown_last_seen = {}
        self.unknown_best_frame = {}
        self.unknown_best_conf = {}

        self.reported_unknown_tids = set()

        self.last_known_seen_time = None

        self.min_unknown_seconds = config.UNKNOWN_EVENT_MIN_SECONDS
        self.known_cooldown_seconds = config.KNOWN_PERSON_COOLDOWN_SECONDS

    def update_known_seen(self, name):
        if name and name != "Unknown":
            self.last_known_seen_time = time.time()

    def update_unknown_candidate(self, frame, track_id, box=None, confidence=None):
        if track_id is None:
            return

        if track_id < 0:
            return

        if track_id in self.reported_unknown_tids:
            return

        now = time.time()

        if track_id not in self.unknown_first_seen:
            self.unknown_first_seen[track_id] = now
            print(f"[UNKNOWN EVENT] TID {track_id} first seen as Unknown")

        self.unknown_last_seen[track_id] = now

        event_image = self._make_event_image(frame, box)

        if event_image is not None:
            if track_id not in self.unknown_best_frame:
                self.unknown_best_frame[track_id] = event_image
                self.unknown_best_conf[track_id] = confidence or 0.0
            else:
                old_conf = self.unknown_best_conf.get(track_id, 0.0)
                new_conf = confidence or 0.0

                if new_conf > old_conf:
                    self.unknown_best_frame[track_id] = event_image
                    self.unknown_best_conf[track_id] = new_conf

        self._maybe_report(track_id)

    def _maybe_report(self, track_id):
        now = time.time()

        first_seen = self.unknown_first_seen.get(track_id)

        if first_seen is None:
            return

        unknown_duration = now - first_seen

        if unknown_duration < self.min_unknown_seconds:
            return

        if self.last_known_seen_time is not None:
            seconds_since_known = now - self.last_known_seen_time

            if seconds_since_known < self.known_cooldown_seconds:
                print(
                    f"[UNKNOWN EVENT] TID {track_id} blocked; "
                    f"known person seen {seconds_since_known:.1f}s ago"
                )
                return

        image = self.unknown_best_frame.get(track_id)

        if image is None:
            print(f"[UNKNOWN EVENT] TID {track_id} has no image to upload")
            return

        confidence = self.unknown_best_conf.get(track_id)

        metadata = {
            "rule": "unknown_seen_min_seconds_and_no_known_recently",
            "unknown_duration_seconds": round(unknown_duration, 1),
            "min_unknown_seconds": self.min_unknown_seconds,
            "known_cooldown_seconds": self.known_cooldown_seconds,
        }

        ok = self.cloud_client.send_unknown_person_event(
            frame=image,
            track_id=track_id,
            confidence=confidence,
            metadata=metadata,
        )

        if ok:
            self.reported_unknown_tids.add(track_id)
            print(f"[UNKNOWN EVENT] TID {track_id} reported once")

    def cleanup(self, max_missing_seconds=15.0):
        """
        Remove stale unknown candidates that disappeared before being reported.
        Do not remove reported_unknown_tids, because we want one event per TID.
        """

        now = time.time()
        stale_tids = []

        for tid, last_seen in self.unknown_last_seen.items():
            if now - last_seen > max_missing_seconds:
                stale_tids.append(tid)

        for tid in stale_tids:
            self.unknown_first_seen.pop(tid, None)
            self.unknown_last_seen.pop(tid, None)
            self.unknown_best_frame.pop(tid, None)
            self.unknown_best_conf.pop(tid, None)

    def _make_event_image(self, frame, box):
        if frame is None:
            return None

        if box is None:
            return frame.copy()

        h, w = frame.shape[:2]
        x1, y1, x2, y2 = box

        x1 = int(x1)
        y1 = int(y1)
        x2 = int(x2)
        y2 = int(y2)

        pad_x = int((x2 - x1) * 0.15)
        pad_y = int((y2 - y1) * 0.15)

        x1 = max(0, x1 - pad_x)
        y1 = max(0, y1 - pad_y)
        x2 = min(w, x2 + pad_x)
        y2 = min(h, y2 + pad_y)

        if x2 <= x1 or y2 <= y1:
            return frame.copy()

        crop = frame[y1:y2, x1:x2]

        if crop.size == 0:
            return frame.copy()

        return crop.copy()