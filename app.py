# app.py

import threading
import time

import cv2
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from vision.camera import Camera
from vision.detector import YOLOTracker
from vision.recognition import FaceIdentifier
from vision.pipeline import TrackRecognizePipeline

from shared.state import SystemState
from tracking.follow_controller import FollowController
from tracking.servo_controller import ServoController
from tracking.servo_command_worker import ServoCommandWorker


# --------------------------------------------------
# Runtime objects
# --------------------------------------------------

camera = None
tracker = None
face_id = None
state = None
servo = None
servo_worker = None
follow_controller = None
pipeline = None
pipeline_thread = None

runtime_started = False
runtime_lock = threading.Lock()


# --------------------------------------------------
# FastAPI setup
# --------------------------------------------------

app = FastAPI(title="RPi Camera System API")


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # simple for local dev / EC2 frontend testing
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --------------------------------------------------
# Request models
# --------------------------------------------------

class StepRequest(BaseModel):
    step: float = 2.0


class MoveToRequest(BaseModel):
    pan: float
    tilt: float


# --------------------------------------------------
# Runtime startup
# --------------------------------------------------

def start_runtime_once():
    global camera
    global tracker
    global face_id
    global state
    global servo
    global servo_worker
    global follow_controller
    global pipeline
    global pipeline_thread
    global runtime_started

    with runtime_lock:
        if runtime_started:
            return

        print("###############################")
        print("Starting surveillance API runtime...")
        print("Auto-detecting camera...")

        camera = Camera()

        print("Loading tracker and face recognition...")
        tracker = YOLOTracker()
        face_id = FaceIdentifier()

        state = SystemState()
        state.mode = "manual"

        servo = ServoController(
            pan_pin=23,
            tilt_pin=18,
        )

        servo_worker = ServoCommandWorker(servo)

        follow_controller = FollowController(
            state,
            servo_worker,
        )

        pipeline = TrackRecognizePipeline(
            camera,
            tracker,
            face_id,
            state,
            follow_controller,
            servo_worker,
        )

        pipeline_thread = threading.Thread(
            target=pipeline.run,
            daemon=True,
        )
        pipeline_thread.start()

        runtime_started = True

        print("[API RUNTIME] Started")


@app.on_event("startup")
def on_startup():
    start_runtime_once()


# --------------------------------------------------
# Helpers
# --------------------------------------------------

def require_runtime():
    if not runtime_started:
        start_runtime_once()


def clear_target_state():
    state.target_x = None
    state.target_y = None
    state.tracked_id = None


def reset_follow_controller():
    if follow_controller is None:
        return

    if hasattr(follow_controller, "tracking"):
        follow_controller.tracking = False

    if hasattr(follow_controller, "detection_counter"):
        follow_controller.detection_counter = 0

    if hasattr(follow_controller, "lost_counter"):
        follow_controller.lost_counter = 0


def get_servo_pan():
    if servo is None:
        return None
    return getattr(servo, "pan", None)


def get_servo_tilt():
    if servo is None:
        return None
    return getattr(servo, "tilt", None)


# --------------------------------------------------
# Basic endpoints
# --------------------------------------------------

@app.get("/")
def root():
    return {
        "ok": True,
        "name": "RPi Camera System API",
    }


@app.get("/status")
def get_status():
    require_runtime()

    return {
        "ok": True,
        "mode": state.mode,
        "pan": get_servo_pan(),
        "tilt": get_servo_tilt(),
        "target_x": state.target_x,
        "target_y": state.target_y,
        "frame_width": state.frame_width,
        "frame_height": state.frame_height,
        "tracked_id": state.tracked_id,
        "runtime_started": runtime_started,
    }


# --------------------------------------------------
# Mode endpoints
# --------------------------------------------------

@app.post("/mode/manual")
def set_manual_mode():
    require_runtime()

    state.mode = "manual"
    clear_target_state()
    reset_follow_controller()

    # Optional but recommended:
    # prevent a leftover AI movement command from executing after manual mode starts.
    servo_worker.send("freeze")
    time.sleep(0.05)
    servo_worker.send("unfreeze")

    return {
        "ok": True,
        "mode": state.mode,
    }


@app.post("/mode/follow")
def set_follow_mode():
    require_runtime()

    state.mode = "follow"

    servo_worker.send("unfreeze")

    return {
        "ok": True,
        "mode": state.mode,
    }


# --------------------------------------------------
# AI endpoints
# For your current code, AI is effectively controlled by state.mode.
# These aliases make the future frontend simpler.
# --------------------------------------------------

@app.post("/ai/start")
def start_ai():
    require_runtime()

    state.mode = "follow"
    servo_worker.send("unfreeze")

    return {
        "ok": True,
        "mode": state.mode,
        "ai_enabled": True,
    }


@app.post("/ai/stop")
def stop_ai():
    require_runtime()

    state.mode = "manual"
    clear_target_state()
    reset_follow_controller()

    servo_worker.send("freeze")
    time.sleep(0.05)
    servo_worker.send("unfreeze")

    return {
        "ok": True,
        "mode": state.mode,
        "ai_enabled": False,
    }


# --------------------------------------------------
# Servo endpoints
# --------------------------------------------------

@app.post("/servo/left")
def servo_left(req: StepRequest):
    require_runtime()

    state.mode = "manual"
    clear_target_state()
    reset_follow_controller()

    servo_worker.send("left", req.step)

    return {
        "ok": True,
        "command": "left",
        "step": req.step,
    }


@app.post("/servo/right")
def servo_right(req: StepRequest):
    require_runtime()

    state.mode = "manual"
    clear_target_state()
    reset_follow_controller()

    servo_worker.send("right", req.step)

    return {
        "ok": True,
        "command": "right",
        "step": req.step,
    }


@app.post("/servo/up")
def servo_up(req: StepRequest):
    require_runtime()

    state.mode = "manual"
    clear_target_state()
    reset_follow_controller()

    servo_worker.send("up", req.step)

    return {
        "ok": True,
        "command": "up",
        "step": req.step,
    }


@app.post("/servo/down")
def servo_down(req: StepRequest):
    require_runtime()

    state.mode = "manual"
    clear_target_state()
    reset_follow_controller()

    servo_worker.send("down", req.step)

    return {
        "ok": True,
        "command": "down",
        "step": req.step,
    }


@app.post("/servo/center")
def servo_center():
    require_runtime()

    state.mode = "manual"
    clear_target_state()
    reset_follow_controller()

    servo_worker.send("center")

    return {
        "ok": True,
        "command": "center",
    }


@app.post("/servo/move_to")
def servo_move_to(req: MoveToRequest):
    require_runtime()

    servo_worker.send(
        "move_to",
        (req.pan, req.tilt),
    )

    return {
        "ok": True,
        "command": "move_to",
        "pan": req.pan,
        "tilt": req.tilt,
    }


@app.post("/servo/freeze")
def servo_freeze():
    require_runtime()

    servo_worker.send("freeze")

    return {
        "ok": True,
        "command": "freeze",
    }


@app.post("/servo/unfreeze")
def servo_unfreeze():
    require_runtime()

    servo_worker.send("unfreeze")

    return {
        "ok": True,
        "command": "unfreeze",
    }


# --------------------------------------------------
# Video feed
# --------------------------------------------------

def generate_video_frames():
    require_runtime()

    while True:
        if pipeline is None:
            time.sleep(0.05)
            continue

        frame = pipeline.get_latest_frame()

        if frame is None:
            time.sleep(0.05)
            continue

        success, buffer = cv2.imencode(".jpg", frame)

        if not success:
            continue

        jpg_bytes = buffer.tobytes()

        yield (
            b"--frame\r\n"
            b"Content-Type: image/jpeg\r\n\r\n"
            + jpg_bytes
            + b"\r\n"
        )


@app.get("/video_feed")
def video_feed():
    return StreamingResponse(
        generate_video_frames(),
        media_type="multipart/x-mixed-replace; boundary=frame",
    )

