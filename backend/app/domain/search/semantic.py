from __future__ import annotations

import logging
import os
from functools import lru_cache
from pathlib import Path
from typing import Any

import numpy as np

from app.core.config import settings

try:  # pragma: no cover - optional dependency used only for semantic normalization
    from sklearn.preprocessing import normalize as _sklearn_l2_normalize
except ImportError:  # pragma: no cover - fallback is covered instead
    _sklearn_l2_normalize = None

try:  # pragma: no cover - optional dependency for vector search acceleration
    import faiss
except ImportError:  # pragma: no cover - fallback path is covered instead
    faiss = None

_BGE_IMPORT_ERROR: Exception | None = None
try:  # pragma: no cover - optional dependency for dense embeddings
    from FlagEmbedding import BGEM3FlagModel
except ImportError as exc:  # pragma: no cover - fallback path is covered instead
    BGEM3FlagModel = None
    _BGE_IMPORT_ERROR = exc


LOGGER = logging.getLogger(__name__)

SEMANTIC_BACKEND_BGE_M3 = "bge_m3"
SEMANTIC_BACKEND_FALLBACK = "tfidf_svd"


def encode_bge_m3_texts(texts: list[str]) -> np.ndarray | None:
    cleaned_texts = [
        stripped if (stripped := (text or "").strip()) else " "
        for text in texts
    ]
    if not any(text.strip() for text in cleaned_texts):
        return None

    model = _load_bge_m3_model(
        settings.search_semantic_model_name,
        settings.search_semantic_use_fp16,
    )
    if model is None:
        return None

    try:
        encoded = model.encode(
            cleaned_texts,
            batch_size=settings.search_semantic_batch_size,
            max_length=settings.search_semantic_max_length,
        )
    except Exception as exc:  # pragma: no cover - depends on optional runtime model state
        LOGGER.warning("Failed to encode texts with BGE-M3: %s", exc)
        return None

    dense_vectors = encoded.get("dense_vecs") if isinstance(encoded, dict) else encoded
    return _normalize_embeddings(dense_vectors)


def build_faiss_index(embeddings: np.ndarray) -> Any | None:
    if (
        faiss is None
        or not settings.search_semantic_use_faiss
        or embeddings.size == 0
        or embeddings.ndim != 2
    ):
        return None

    try:  # pragma: no cover - optional dependency
        index = faiss.IndexFlatIP(int(embeddings.shape[1]))
        index.add(np.ascontiguousarray(embeddings.astype(np.float32)))
        return index
    except Exception as exc:  # pragma: no cover - depends on optional runtime state
        LOGGER.warning("Failed to build FAISS semantic index: %s", exc)
        return None


@lru_cache(maxsize=2)
def _load_bge_m3_model(
    model_name: str,
    use_fp16: bool,
) -> Any | None:
    if BGEM3FlagModel is None:
        if _BGE_IMPORT_ERROR is not None:
            LOGGER.warning(
                "FlagEmbedding import failed before BGE-M3 initialization: %s",
                _BGE_IMPORT_ERROR,
            )
        return None

    if (
        not settings.search_semantic_allow_remote_download
        and not _is_model_cached_locally(model_name)
    ):
        LOGGER.info(
            "Skipping BGE-M3 initialization for '%s': remote download is disabled "
            "and no local cache was found",
            model_name,
        )
        return None

    resolved_model_name = _resolve_local_model_reference(model_name)

    try:  # pragma: no cover - depends on optional runtime model availability
        model = BGEM3FlagModel(resolved_model_name, use_fp16=use_fp16)
    except Exception as exc:  # pragma: no cover - depends on optional runtime model availability
        LOGGER.warning(
            "Failed to initialize BGE-M3 model '%s' (resolved=%s): %s",
            model_name,
            resolved_model_name,
            exc,
        )
        return None
    LOGGER.info(
        "Initialized BGE-M3 model '%s' from %s",
        model_name,
        resolved_model_name,
    )
    return model


def _normalize_embeddings(values: Any) -> np.ndarray | None:
    if values is None:
        return None

    matrix = np.asarray(values, dtype=np.float32)
    if matrix.ndim == 1:
        matrix = matrix.reshape(1, -1)
    if matrix.size == 0:
        return None

    normalized = _l2_normalize(matrix)
    return np.asarray(normalized, dtype=np.float32)


def _l2_normalize(matrix: np.ndarray) -> np.ndarray:
    if _sklearn_l2_normalize is not None:
        return _sklearn_l2_normalize(matrix)

    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    safe_norms = np.where(norms > 0, norms, 1.0)
    return matrix / safe_norms


def _is_model_cached_locally(model_name: str) -> bool:
    if _resolve_cached_model_snapshot_path(model_name) is not None:
        return True

    model_path = Path(model_name).expanduser()
    if model_path.exists():
        return True

    return False


def _resolve_local_model_reference(model_name: str) -> str:
    model_path = Path(model_name).expanduser()
    if model_path.exists():
        return str(model_path)

    snapshot_path = _resolve_cached_model_snapshot_path(model_name)
    if snapshot_path is not None:
        return str(snapshot_path)

    return model_name


def _resolve_cached_model_snapshot_path(model_name: str) -> Path | None:
    snapshot_root_name = f"models--{model_name.replace('/', '--')}"
    for cache_root in _iter_huggingface_cache_roots():
        snapshots_dir = cache_root / snapshot_root_name / "snapshots"
        if not snapshots_dir.is_dir():
            continue
        try:
            snapshots = sorted(
                child
                for child in snapshots_dir.iterdir()
                if child.is_dir()
            )
            if snapshots:
                return snapshots[-1]
        except OSError:
            continue

    return None


def _iter_huggingface_cache_roots() -> tuple[Path, ...]:
    candidate_roots: list[Path] = []
    env_values = [
        os.getenv("HUGGINGFACE_HUB_CACHE"),
        os.getenv("TRANSFORMERS_CACHE"),
    ]
    hf_home = os.getenv("HF_HOME")
    if hf_home:
        env_values.append(str(Path(hf_home).expanduser() / "hub"))
    env_values.append(str(Path.home() / ".cache" / "huggingface" / "hub"))

    seen: set[Path] = set()
    for raw_value in env_values:
        if not raw_value:
            continue
        path = Path(raw_value).expanduser()
        if path in seen:
            continue
        seen.add(path)
        candidate_roots.append(path)

    return tuple(candidate_roots)
