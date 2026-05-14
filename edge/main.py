from camera import Camera
from detector import YOLOTracker
from recognition import FaceIdentifier
from pipeline import TrackRecognizePipeline

def main():
    print("###############################")
    print("Starting surveillance system...")
    print("Auto-detecting camera...")

    camera = Camera()

    print("###############################")
    tracker = YOLOTracker()
    face_id = FaceIdentifier()

    pipeline = TrackRecognizePipeline(camera, tracker, face_id)
    pipeline.run()

if __name__ == "__main__":
    main()
