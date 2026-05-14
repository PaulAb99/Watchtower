from camera import Camera
from detector import YOLOTracker
from recognition import FaceIdentifier
from pipeline import TrackRecognizePipeline
import config

def main():
    camera = Camera(config.CAMERA_INDEX)
    tracker = YOLOTracker()
    face_id = FaceIdentifier()

    pipeline = TrackRecognizePipeline(camera, tracker, face_id)
    pipeline.run()

if __name__ == "__main__":
    main()