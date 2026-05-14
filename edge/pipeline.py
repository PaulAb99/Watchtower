import cv2
import config

class TrackRecognizePipeline:
    def __init__(self, camera, tracker, face_id):
        self.camera = camera
        self.tracker = tracker
        self.face_id = face_id

        self.frame_idx = 0
        self.names_by_track = {} #track_id-name
        self.ttl_by_track = {}  #track_id-frames remaining

        self.prev_center = None
        self.alpha = 0.7  # smoothing

    def _decay_cache(self):#time to live for tid's
        dead = []

        for tid in list(self.ttl_by_track.keys()): 
            self.ttl_by_track[tid] -= 1
            if self.ttl_by_track[tid] <= 0:
                dead.append(tid)

        for tid in dead:
            self.ttl_by_track.pop(tid, None)
            self.names_by_track.pop(tid, None)

    @staticmethod
    def _safe_crop(frame, box):
        h, w = frame.shape[:2]
        x1, y1, x2, y2 = box
        x1 = max(0, min(w - 1, x1))
        x2 = max(0, min(w, x2))
        y1 = max(0, min(h - 1, y1))
        y2 = max(0, min(h, y2))
        if x2 <= x1 or y2 <= y1:
            return None
        return frame[y1:y2, x1:x2]

    def run(self):
        while True:

            #capture frames ------------------------------

            frame = self.camera.read()

            if frame is None:
                continue

            self.frame_idx += 1

            #memory --------------------------------------
            self._decay_cache() 


            #tracking---------------------------
            dets = self.tracker.track(frame)
            

            #select recognition target --------------------
            main_target = None
            tracked=None
            person_dets = [d for d in dets if d.get("label") == "person"]

            if person_dets:
                main_target = max(person_dets,key=lambda d: (d["box"][2] - d["box"][0]) * (d["box"][3] - d["box"][1]))
                tracked= main_target["track_id"]
           
                
            if main_target:
                x1, y1, x2, y2 = main_target["box"]
                
                cx = (x1 + x2) // 2
                cy = (y1 + y2) // 2

                if self.prev_center is None:
                    smoothed = (cx, cy)
                else:
                    smoothed = (
                        int(self.alpha * self.prev_center[0] + (1 - self.alpha) * cx),
                        int(self.alpha * self.prev_center[1] + (1 - self.alpha) * cy),
                )

                self.prev_center = smoothed

        
            # recognition-------------------------------
            do_face = (self.frame_idx % config.FACE_SCAN_EVERY_N_FRAMES == 0)
            
            
            if do_face:
                for d in dets:
                    tid = d["track_id"]

                    if tid < 0:
                        continue

                    # cached skip
                    if tid in self.names_by_track and self.ttl_by_track.get(tid, 0) > 0:
                        continue

                    crop = self._safe_crop(frame, d["box"])
                    if crop is None:
                        continue
                    
                    #actual recognition
                    result = self.face_id.identify_from_person_crop(crop)
                    name = result["name"]

                    self.names_by_track[tid] = name
                    self.ttl_by_track[tid] = config.TRACK_NAME_TTL_FRAMES



            annotated = self.tracker.draw(frame, dets, tracked, self.names_by_track)
            cv2.imshow("Multiple Obj Detection - Main Obj Tracking", annotated)
            
            counts = {}
            for d in dets:
                label = d["label"]
                counts[label] = counts.get(label, 0) + 1

            print(counts)

            if cv2.waitKey(1) & 0xFF == 27:  # ESC 2 quit



                break

        self.camera.release()
        cv2.destroyAllWindows()