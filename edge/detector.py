from ultralytics import YOLO
import config

class YOLOTracker:
    def __init__(self):
        self.model = YOLO(config.YOLO_MODEL)

    def track(self, frame):    
        
        if config.PERSONS_CAT_DOG: 
            classes = [0, 15, 16] 
        elif config.ONLY_PERSON:
            classes = [0]
        else:
            classes = None

        results = self.model.track(
            frame,
            persist=config.TRACK_PERSIST,
            tracker=config.TRACKER_CONFIG,
            conf=config.CONFIDENCE_THRESHOLD,
            classes=classes,
            verbose=False,
        )
        

        # create [{track_id:int, box:(x1,y1,x2,y2), conf:float}] to return 

        dets = []
        r0 = results[0]
        if r0.boxes is None or len(r0.boxes) == 0:
            return dets
       
        boxes = r0.boxes
        ids = boxes.id  # may be None on first frames

        for i in range(len(boxes)):
            xyxy = boxes.xyxy[i].tolist()
            conf = float(boxes.conf[i])
            cls_id = int(boxes.cls[i])
            label = self.model.names[cls_id]
            
            if label in ["cat", "dog"] and conf < 0.7:
                continue

            track_id = int(ids[i]) if ids is not None else -1

            x1, y1, x2, y2 = map(int, xyxy)

            dets.append({
                "track_id": track_id,
                "box": (x1, y1, x2, y2),
                "conf": conf,
                "cls_id": cls_id,
                "label": label
            })

        return dets

    @staticmethod
    def draw(frame, dets, tracked, names_by_id=None):
        import cv2
        names_by_id = names_by_id or {}

        for d in dets:
            x1, y1, x2, y2 = d["box"]
            tid = d["track_id"]
            conf = d["conf"]
            yolo_label = d.get("label", "object")


            identity = names_by_id.get(tid, None)
            
            if yolo_label == "person":
                label = identity if identity and identity != "Unknown" else "Unknown Person"
            else:
                label = yolo_label

           

            final_label = f"{label} ({conf:.2f})"

            if tracked is not None and tid == tracked:
                cv2.rectangle(frame, (x1, y1), (x2, y2), (200, 0, 100), 2)
                cv2.putText(frame, final_label +" Tid:"+str(tid)  + '(tracked)', (x1, max(0, y1 - 10)),cv2.FONT_HERSHEY_SIMPLEX, 0.6, (200, 0, 100), 2)
            else:
                cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
                cv2.putText(frame, final_label +" Tid:"+str(tid) , (x1, max(0, y1 - 10)),cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
        
        
        return frame