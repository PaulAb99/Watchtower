import os
import cv2
import numpy as np
from insightface.app import FaceAnalysis
import config

def _l2_normalize(v: np.ndarray) -> np.ndarray:
    n = np.linalg.norm(v)
    return v if n == 0 else v / n

class FaceIdentifier:
    """
    Loads a small face database from KNOWN_FACES_DIR:
      known_faces/Name/*.jpg
    Builds embeddings and matches with cosine similarity.
    """
    def __init__(self):
        self.app = FaceAnalysis(name="buffalo_l")  # solid default
        # ctx_id=0 for GPU, -1 for CPU
        self.app.prepare(ctx_id=-1, det_size=config.FACE_DET_SIZE)

        self.db_names = []
        self.db_embs = []  # list[np.ndarray]
        self._load_database(config.KNOWN_FACES_DIR)

    def _load_database(self, root_dir: str):
        if not os.path.isdir(root_dir):
            print(f"[FaceIdentifier] No folder: {root_dir} (skipping DB load)")
            return

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

                # take the largest face if multiple
                faces.sort(key=lambda f: (f.bbox[2]-f.bbox[0])*(f.bbox[3]-f.bbox[1]), reverse=True)
                emb = _l2_normalize(faces[0].embedding.astype(np.float32))

                self.db_names.append(person_name)
                self.db_embs.append(emb)

        if self.db_embs:
            self.db_embs = np.stack(self.db_embs, axis=0)
            print(f"[FaceIdentifier] Loaded {len(self.db_names)} face embeddings.")
        else:
            self.db_embs = np.zeros((0, 512), dtype=np.float32)
            print("[FaceIdentifier] Loaded 0 embeddings (DB empty?).")

    def identify_from_person_crop(self, person_crop_bgr: np.ndarray):
        """
        Takes a cropped person image (BGR). Tries to find a face inside and identify it.
        Returns (name:str, score:float) or ("Unknown", 0.0)
        """
        if self.db_embs.shape[0] == 0:
            return {
                        "name": "Unknown",
                        "score": 0
            }

        faces = self.app.get(person_crop_bgr)
        if not faces:
            return {
                        "name": "Unknown",
                        "score": 0
            }
        faces = [
            f for f in faces
            if (f.bbox[2] - f.bbox[0]) > 50 and (f.bbox[3] - f.bbox[1]) > 50
        ]


        if not faces:
            return {
                        "name": "Unknown",
                        "score": 0
            }
        # largest face
        faces.sort(key=lambda f: (f.bbox[2]-f.bbox[0])*(f.bbox[3]-f.bbox[1]), reverse=True)
        emb = _l2_normalize(faces[0].embedding.astype(np.float32))

        # cosine similarity: dot product of normalized vectors
        sims = (self.db_embs @ emb)
        best_idx = int(np.argmax(sims))
        best_sim = float(sims[best_idx])

        # Convert similarity to a simple decision using a threshold.
        # Higher is better. Typical “good” sims often > 0.35–0.5 depending on data.
        if best_sim >= config.FACE_SIM_THRESHOLD:
            return {
                        "name": self.db_names[best_idx],
                        "score": best_sim
            }

        return {
                    "name": "Unknown",
                    "score": best_sim
        }