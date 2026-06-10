from vision import camera
from vision.camera import Camera
from vision.detector import YOLOTracker
from vision.recognition import FaceIdentifier
from vision.pipeline import TrackRecognizePipeline


from shared.state import SystemState
from tracking.follow_controller import FollowController


from tracking.simple_pan_tilt import SimplePanTilt

def main():
    print("###############################")
    print("Starting surveillance system...")
    print("Auto-detecting camera...")

    camera = Camera()

    print("###############################")
    tracker = YOLOTracker()
    face_id = FaceIdentifier()

    state = SystemState()
    state.mode = "follow"
    

    servo = SimplePanTilt(pan_pin=23, tilt_pin=18)

    follow_controller = FollowController(state, servo)
    pipeline = TrackRecognizePipeline(camera, tracker, face_id, state, follow_controller, servo)


    pipeline.run()

   

if __name__ == "__main__":
    main()
