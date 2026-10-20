"""
Лица: детектор YuNet и распознавание SFace из OpenCV Zoo (Apache-2.0/MIT, ONNX, быстро на CPU).
Модели скачиваются при сборке образа, а локально — при первом использовании.
"""

import asyncio
import logging
import threading
import urllib.request
from collections.abc import Sequence
from pathlib import Path

import cv2
import numpy as np
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from src.application.people.ports import DetectedFace, FaceAnalyzer
from src.domain.common import Box

logger = logging.getLogger(__name__)

_ZOO = "https://github.com/opencv/opencv_zoo/raw/main/models"
DETECTOR_URL = f"{_ZOO}/face_detection_yunet/face_detection_yunet_2023mar.onnx"
RECOGNIZER_URL = f"{_ZOO}/face_recognition_sface/face_recognition_sface_2021dec.onnx"

_MAX_SIDE = 1600
_THUMBNAIL_SIZE = 160


class FacesConfig(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="FACES_")

    models_dir: Path = Path(".models")
    min_detection_score: float = Field(default=0.85, description="Уверенность детектора")
    min_face_size: int = Field(default=40, description="Минимальная сторона лица, px")
    same_person_score: float = Field(
        default=0.42, description="Косинусное сходство SFace (рекомендация OpenCV — 0.363, берём строже)"
    )


def ensure_models(models_dir: Path) -> tuple[Path, Path]:
    models_dir.mkdir(parents=True, exist_ok=True)
    paths = []

    for url in (DETECTOR_URL, RECOGNIZER_URL):
        path = models_dir / url.rsplit("/", 1)[1]
        if not path.exists():
            logger.info("Downloading face model %s", path.name)
            urllib.request.urlretrieve(url, path)
        paths.append(path)

    return paths[0], paths[1]


class OpenCvFaceAnalyzer(FaceAnalyzer):
    def __init__(self, config: FacesConfig) -> None:
        self._config = config
        self.same_person_score = config.same_person_score
        self._lock = threading.Lock()
        self._detector: cv2.FaceDetectorYN | None = None
        self._recognizer: cv2.FaceRecognizerSF | None = None

    def _models(self) -> tuple[cv2.FaceDetectorYN, cv2.FaceRecognizerSF]:
        if self._detector is None or self._recognizer is None:
            detector_path, recognizer_path = ensure_models(self._config.models_dir)
            self._detector = cv2.FaceDetectorYN.create(
                str(detector_path), "", (320, 320), score_threshold=self._config.min_detection_score
            )
            self._recognizer = cv2.FaceRecognizerSF.create(str(recognizer_path), "")

        return self._detector, self._recognizer

    def _detect(self, data: bytes) -> list[DetectedFace]:
        image = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
        if image is None:
            return []

        scale = min(1.0, _MAX_SIDE / max(image.shape[:2]))
        if scale < 1:
            image = cv2.resize(image, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)

        height, width = image.shape[:2]

        # Модели OpenCV не потокобезопасны
        with self._lock:
            detector, recognizer = self._models()
            detector.setInputSize((width, height))
            _, faces = detector.detect(image)

            result = []
            for face in faces if faces is not None else []:
                x, y, w, h = (float(value) for value in face[:4])
                if min(w, h) < self._config.min_face_size:
                    continue

                feature = recognizer.feature(recognizer.alignCrop(image, face)).flatten()
                vector = feature / (np.linalg.norm(feature) or 1.0)
                x, y = max(x, 0.0), max(y, 0.0)
                w, h = min(w, width - x), min(h, height - y)

                result.append(
                    DetectedFace(
                        box=Box(x=x / width, y=y / height, width=w / width, height=h / height),
                        vector=vector.astype(float).tolist(),
                        score=float(face[14]),
                        thumbnail=_thumbnail(image, x, y, w, h),
                    )
                )

        return result

    async def detect(self, image: bytes) -> list[DetectedFace]:
        return await asyncio.to_thread(self._detect, image)

    def similarity(self, first: Sequence[float], second: Sequence[float]) -> float:
        return float(np.dot(np.asarray(first), np.asarray(second)))


def _thumbnail(image: np.ndarray, x: float, y: float, w: float, h: float) -> bytes:
    """Квадрат вокруг лица с запасом."""

    side = max(w, h) * 1.4
    cx, cy = x + w / 2, y + h / 2
    top, left = int(max(cy - side / 2, 0)), int(max(cx - side / 2, 0))
    crop = image[top : int(cy + side / 2), left : int(cx + side / 2)]
    crop = cv2.resize(crop, (_THUMBNAIL_SIZE, _THUMBNAIL_SIZE), interpolation=cv2.INTER_AREA)
    _, encoded = cv2.imencode(".webp", crop, [cv2.IMWRITE_WEBP_QUALITY, 85])
    return encoded.tobytes()


__all__ = ["FacesConfig", "OpenCvFaceAnalyzer", "ensure_models"]
