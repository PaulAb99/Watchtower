import cv2
import config

class TrackRecognizePipeline:
    def __init__(self, camera, tracker, face_id):
        self.camera = camera
        self.tracker = tracker
        self.face_id = face_id

        self.frame_idx = 0
        self.names_by_track = {}
        self.ttl_by_track = {}
        self.max_cached_tracks = 50
        self.track_order = []  # FIFO eviction

        self.prev_center = None
        self.alpha = 0.7  # smoothing

    def _decay_cache(self):
        dead = []

        for tid in list(self.ttl_by_track.keys()):
            self.ttl_by_track[tid] -= 1
            if self.ttl_by_track[tid] <= 0:
                dead.append(tid)

        for tid in dead:
            self.ttl_by_track.pop(tid, None)
            self.names_by_track.pop(tid, None)
            if tid in self.track_order:
                self.track_order.remove(tid)


        # max cache size
        if len(self.names_by_track) > self.max_cached_tracks:
            excess = len(self.names_by_track) - self.max_cached_tracks
            for _ in range(excess):
                if self.track_order:
                    oldest_tid = self.track_order.pop(0)
                    self.names_by_track.pop(oldest_tid, None)
                    self.ttl_by_track.pop(oldest_tid, None)

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

            #capture frames with frame skipping---------
            frame = self.camera.read_skip()

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

        
            # recognition with smart selection & batch processing
            do_face = (self.frame_idx % config.FACE_SCAN_EVERY_N_FRAMES == 0)

            if do_face:
                person_dets = [d for d in dets if d.get("label") == "person" and d.get("conf", 0) >= config.FACE_MIN_PERSON_CONF]

                # sort by size take top n 
                person_dets.sort(key=lambda d: (d["box"][2] - d["box"][0]) * (d["box"][3] - d["box"][1]), reverse=True)
                person_dets = person_dets[:config.FACE_PROCESS_TOP_N]

                # crops for batch
                crops_to_process = []
                indices_to_process = []

                for i, d in enumerate(person_dets):
                    tid = d["track_id"]

                    if tid < 0:
                        continue

                    # skip cached
                    ttl_remaining = self.ttl_by_track.get(tid, 0)
                    max_ttl = config.TRACK_NAME_TTL_FRAMES
                    if tid in self.names_by_track and ttl_remaining > max_ttl * 0.5:
                        continue

                    crop = self._safe_crop(frame, d["box"])
                    if crop is None:
                        continue

                    crops_to_process.append(crop)
                    indices_to_process.append(i)

                # process batch if any crops
                if crops_to_process:
                    results = self.face_id.identify_batch(crops_to_process)

                    for result_idx, det_idx in enumerate(indices_to_process):
                        d = person_dets[det_idx]
                        tid = d["track_id"]
                        result = results[result_idx]
                        name = result["name"]
                        score = result["score"]

                        # track new ids
                        if tid not in self.names_by_track:
                            self.track_order.append(tid)

                        self.names_by_track[tid] = name

                        # adapt to confidence
                        if name != "Unknown":
                            if score >= config.FACE_SIM_THRESHOLD_HIGH:
                                self.ttl_by_track[tid] = config.TRACK_NAME_TTL_FRAMES * 2  # 120 fps
                            elif score >= config.FACE_SIM_THRESHOLD_LOW:
                                self.ttl_by_track[tid] = config.TRACK_NAME_TTL_FRAMES // 2  # 30 fps
                            else:
                                self.ttl_by_track[tid] = config.TRACK_NAME_TTL_FRAMES  # 60 fps
                        else:
                            self.ttl_by_track[tid] = 0  # unknown



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