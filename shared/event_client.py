import json
import cv2
import requests
import config


class CloudEventClient:
    def __init__(self):
        self.base_url = config.CLOUD_API_BASE_URL.rstrip("/")
        self.system_id = config.CLOUD_SYSTEM_ID

    def send_unknown_person_event(self, frame, track_id, confidence=None, metadata=None):
        if frame is None:
            print("[CLOUD EVENT] No frame provided")
            return False

        success, buffer = cv2.imencode(
            ".jpg",
            frame,
            [int(cv2.IMWRITE_JPEG_QUALITY), 80],
        )

        if not success:
            print("[CLOUD EVENT] Failed to encode image")
            return False

        files = {
            "image": (
                f"unknown_tid_{track_id}.jpg",
                buffer.tobytes(),
                "image/jpeg",
            )
        }

        data = {
            "system_id": str(self.system_id),
            "event_type": "unknown_person_detected",
            "label": "Unknown",
            "confidence": "" if confidence is None else str(confidence),
            "track_id": str(track_id),
            "metadata_json": json.dumps(metadata or {}),
        }

        try:
            response = requests.post(
                f"{self.base_url}/api/dev/events/with-image",
                data=data,
                files=files,
                timeout=5,
            )

            if response.status_code >= 400:
                print(
                    f"[CLOUD EVENT] Upload failed "
                    f"{response.status_code}: {response.text}"
                )
                return False

            print(f"[CLOUD EVENT] Uploaded unknown person event for TID {track_id}")
            return True

        except requests.RequestException as exc:
            print(f"[CLOUD EVENT] Request failed: {exc}")
            return False