import json

import cv2
import requests

import config


class CloudEventClient:
    def __init__(self):
        self.base_url = config.CLOUD_API_BASE_URL.rstrip("/")
        self.system_id = config.CLOUD_SYSTEM_ID

    def send_unknown_person_event(
        self,
        frame,
        track_id=None,
        confidence=None,
        metadata=None,
    ):
        url = f"{self.base_url}/dev/events/with-image"

        print(f"[CLOUD EVENT] Uploading to {url}")
        print(f"[CLOUD EVENT] system_id={self.system_id}")

        ok, buffer = cv2.imencode(".jpg", frame)

        if not ok:
            print("[CLOUD EVENT] Failed to encode frame")
            return False

        files = {
            "image": (
                "unknown_person.jpg",
                buffer.tobytes(),
                "image/jpeg",
            )
        }

        data = {
            "system_id": str(self.system_id),
            "event_type": "unknown_person",
            "label": "Unknown",
            "metadata_json": json.dumps(metadata or {}),
        }

        if confidence is not None:
            data["confidence"] = str(confidence)

        if track_id is not None:
            data["track_id"] = str(track_id)

        try:
            response = requests.post(
                url,
                data=data,
                files=files,
                timeout=10,
            )

            if response.status_code >= 400:
                print(
                    f"[CLOUD EVENT] Upload failed "
                    f"{response.status_code}: {response.text}"
                )
                return False

            print(f"[CLOUD EVENT] Upload success: {response.text}")
            return True

        except requests.RequestException as exc:
            print(f"[CLOUD EVENT] Upload exception: {exc}")
            return False