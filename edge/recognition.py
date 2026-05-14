import os
import cv2
import numpy as np
from insightface.app import FaceAnalysis
import config

def _l2_normalize(v: np.ndarray) -> np.ndarray:
    n = np.linalg.norm(v)
    return v if n == 0 else v / n

class FaceIdentifier:
    def __init__(self):
        self.app = FaceAnalysis(name="buffalo_l")
        self.app.prepare(ctx_id=-1, det_size=config.FACE_DET_SIZE)

        self.db_names = []
        self.db_embs = []
        self._load_database(config.KNOWN_FACES_DIR)

    def _load_database(self, root_dir: str):

        print("############################")
        print("FaceIdentifier")

        if not os.path.isdir(root_dir):
            print(f"No folder: {root_dir} (skipping DB load)")
            return

        temp_names = []
        temp_embs = []

        for person_name in sorted(os.listdir(root_dir)):
            person_dir = os.path.join(root_dir, person_name)
            if not os.path.isdir(person_dir):
                continue

            for fn in sorted(os.listdir(person_dir)):
                if not fn.lower().endswith((".jpg", ".jpeg", ".png")):
                    continue
                path = os.path.join(person_dir, fn)
                img = cv2.imread(path)
                if img is None:
                    continue

                faces = self.app.get(img)
                if not faces:
                    continue

                faces.sort(key=lambda f: (f.bbox[2]-f.bbox[0])*(f.bbox[3]-f.bbox[1]), reverse=True)
                emb = _l2_normalize(faces[0].embedding.astype(np.float32))

                temp_names.append(person_name)
                temp_embs.append(emb)

        # rm dupes
        if temp_embs:
            temp_embs = np.stack(temp_embs, axis=0)
            unique_indices = [0]
            duplicates_removed = 0

            for i in range(1, len(temp_embs)):
                is_duplicate = False
                for j in unique_indices:
                    sim = float(temp_embs[i] @ temp_embs[j])
                    if sim > 0.95:
                        is_duplicate = True
                        duplicates_removed += 1
                        break
                if not is_duplicate:
                    unique_indices.append(i)

            self.db_names = [temp_names[i] for i in unique_indices]
            self.db_embs = temp_embs[unique_indices]
            print(f"Loaded {len(self.db_names)} unique embeddings ({duplicates_removed} dupes removed).")
        else:
            self.db_embs = np.zeros((0, 512), dtype=np.float32)
            print("Loaded 0 embeddings.")
        print("############################")




    def identify_from_person_crop(self, person_crop_bgr: np.ndarray):
        if self.db_embs.shape[0] == 0:
            return {"name": "Unknown", "score": 0}

        faces = self.app.get(person_crop_bgr)
        if not faces:
            return {"name": "Unknown", "score": 0}

        faces = [f for f in faces if (f.bbox[2] - f.bbox[0]) > 50 and (f.bbox[3] - f.bbox[1]) > 50]
        if not faces:
            return {"name": "Unknown", "score": 0}

        faces.sort(key=lambda f: (f.bbox[2]-f.bbox[0])*(f.bbox[3]-f.bbox[1]), reverse=True)
        emb = _l2_normalize(faces[0].embedding.astype(np.float32))

        sims = (self.db_embs @ emb)
        best_idx = int(np.argmax(sims))
        best_sim = float(sims[best_idx])

        if best_sim >= config.FACE_SIM_THRESHOLD:
            return {"name": self.db_names[best_idx], "score": best_sim}

        return {"name": "Unknown", "score": best_sim}





    def identify_batch(self, person_crops_bgr: list):
        if self.db_embs.shape[0] == 0:
            return [{"name": "Unknown", "score": 0} for _ in person_crops_bgr]

        results = []
        for crop in person_crops_bgr:
            results.append(self._identify_single(crop))

        return results




    def _identify_single(self, person_crop_bgr: np.ndarray):
        if person_crop_bgr is None or person_crop_bgr.size == 0:
            return {"name": "Unknown", "score": 0}

        h, w = person_crop_bgr.shape[:2]
        if h < 80 or w < 80:
            return {"name": "Unknown", "score": 0}

        faces = self.app.get(person_crop_bgr)
        if not faces:
            return {"name": "Unknown", "score": 0}

        faces = [f for f in faces if (f.bbox[2] - f.bbox[0]) > 50 and (f.bbox[3] - f.bbox[1]) > 50]
        if not faces:
            return {"name": "Unknown", "score": 0}

        faces.sort(key=lambda f: (f.bbox[2]-f.bbox[0])*(f.bbox[3]-f.bbox[1]), reverse=True)
        emb = _l2_normalize(faces[0].embedding.astype(np.float32))

        sims = (self.db_embs @ emb)
        best_idx = int(np.argmax(sims))
        best_sim = float(sims[best_idx])

        if best_sim >= config.FACE_SIM_THRESHOLD_LOW:
            return {"name": self.db_names[best_idx], "score": best_sim}

        return {"name": "Unknown", "score": best_sim}
