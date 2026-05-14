
# Camera
CAMERA_INDEX = 0

# Tracking
YOLO_MODEL = "yolov8s-seg.pt"
ONLY_PERSON = False          
PERSONS_CAT_DOG=True
SHOW_YOLO_LABELS = True
CONFIDENCE_THRESHOLD = 0.40
TRACKER_CONFIG = "bytetrack.yaml"   
TRACK_PERSIST = True

# Recognition
KNOWN_FACES_DIR = "edge/known_faces"
FACE_DET_SIZE = (1280,1280)          
FACE_SIM_THRESHOLD = 0.35           
FACE_SCAN_EVERY_N_FRAMES = 5       
TRACK_NAME_TTL_FRAMES = 60          