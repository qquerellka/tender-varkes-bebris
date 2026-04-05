from __future__ import annotations

import csv as csv_mod
import logging
from pathlib import Path

import numpy as np

LOGGER = logging.getLogger(__name__)


class EmbeddingStore:
    """Loads precomputed item embeddings and provides lightweight similarity helpers."""

    def __init__(
        self,
        embeddings_path: Path,
        ste_csv_path: Path | None = None,
    ) -> None:
        self._emb = np.load(str(embeddings_path)).astype(np.float32)
        n_items, self.dim = self._emb.shape

        norms = np.linalg.norm(self._emb, axis=1, keepdims=True)
        safe = np.where(norms > 1e-9, norms, 1.0)
        self._emb = self._emb / safe

        self._id_to_idx: dict[str, int] = {}
        if ste_csv_path and ste_csv_path.exists():
            with ste_csv_path.open("r", encoding="utf-8-sig", newline="") as file:
                reader = csv_mod.reader(file, delimiter=";")
                for idx, row in enumerate(reader):
                    if idx >= n_items:
                        break
                    if not row:
                        continue
                    ste_id = row[0].strip()
                    if ste_id:
                        self._id_to_idx[ste_id] = idx

        LOGGER.info(
            "EmbeddingStore loaded %d embeddings (dim=%d), mapped %d ids",
            n_items,
            self.dim,
            len(self._id_to_idx),
        )

    def get(self, ste_id: str) -> np.ndarray | None:
        idx = self._id_to_idx.get(ste_id)
        if idx is None:
            return None
        return self._emb[idx]

    def centroid(self, ste_ids: list[str]) -> np.ndarray | None:
        vectors = [vector for ste_id in ste_ids if (vector := self.get(ste_id)) is not None]
        if not vectors:
            return None

        centroid = np.mean(vectors, axis=0, dtype=np.float32)
        norm = np.linalg.norm(centroid)
        if norm > 1e-9:
            centroid = centroid / norm
        return centroid

    @staticmethod
    def cosine(a: np.ndarray | None, b: np.ndarray | None) -> float:
        if a is None or b is None:
            return 0.0
        return float(np.dot(a, b))

    def max_sim(self, anchor_ids: list[str], candidate_id: str) -> float:
        candidate = self.get(candidate_id)
        if candidate is None:
            return 0.0

        best = 0.0
        for ste_id in anchor_ids:
            vector = self.get(ste_id)
            if vector is None:
                continue
            similarity = float(np.dot(vector, candidate))
            if similarity > best:
                best = similarity
        return best
