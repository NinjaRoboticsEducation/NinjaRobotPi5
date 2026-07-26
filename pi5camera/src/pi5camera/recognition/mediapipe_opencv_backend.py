"""Face-recognition backend using OpenCV (required) + MediaPipe (optional).

Face detection:
  - Primary:  Google MediaPipe (when available — x86_64 and macOS only)
  - Fallback: OpenCV Haar cascade (always available, works on ARM64)

Face embedding:
  - Primary:  OpenCV DNN with a FaceNet-style ONNX model (when provided)
  - Fallback: Pixel-histogram embedding (always available)

This backend avoids dlib entirely — no C++ compilation needed on
Raspberry Pi 5.
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

from pi5camera.errors import RecognitionError
from pi5camera.models import EncodedFace, FaceBoundingBox


def _try_import_mediapipe() -> Any | None:
    """Return the mediapipe module if available, otherwise ``None``."""
    try:
        import mediapipe as mp

        return mp
    except ImportError:
        return None


def _lazy_import_cv2() -> Any:
    try:
        import cv2

        return cv2
    except ImportError as exc:
        raise RecognitionError(
            "OpenCV is not installed. Install with: pip install opencv-python-headless"
        ) from exc


def _lazy_import_numpy() -> Any:
    try:
        import numpy as np

        return np
    except ImportError as exc:
        raise RecognitionError("NumPy is not installed. Install with: pip install numpy") from exc


def _build_haar_cascade(cv2: Any) -> Any | None:
    """Build an OpenCV Haar cascade classifier for frontal face detection.

    The Haar cascade XML is shipped inside every ``opencv-python-headless``
    package, so this works on all platforms including ARM64.
    """
    cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_alt2.xml"
    cascade = cv2.CascadeClassifier(cascade_path)
    if cascade.empty():
        return None
    return cascade


class MediaPipeOpenCVBackend:
    """Face detection via MediaPipe or OpenCV Haar + embedding via OpenCV DNN.

    When MediaPipe is available (x86_64, macOS) it is used for higher-accuracy
    face detection.  When MediaPipe is **not** available (ARM64 / Raspberry Pi)
    the backend silently falls back to OpenCV's built-in Haar cascade, which
    is always shipped with ``opencv-python-headless``.

    When no ONNX embedding model is supplied the backend falls back to
    a pixel-histogram embedding derived from the face crop.
    """

    def __init__(
        self,
        *,
        model_path: str | None = None,
        min_detection_confidence: float = 0.5,
        embedding_size: int = 128,
    ) -> None:
        self._model_path = model_path
        self._min_detection_confidence = min_detection_confidence
        self._embedding_size = embedding_size
        self._cv2 = _lazy_import_cv2()
        self._np = _lazy_import_numpy()

        # Try MediaPipe first; fall back to Haar cascade.
        self._mp = _try_import_mediapipe()
        self._mp_detector: Any | None = None
        self._haar_cascade: Any | None = None

        if self._mp is not None:
            try:
                self._mp_detector = self._mp.solutions.face_detection.FaceDetection(
                    model_selection=1,
                    min_detection_confidence=self._min_detection_confidence,
                )
            except Exception:
                self._mp = None

        if self._mp_detector is None:
            self._haar_cascade = _build_haar_cascade(self._cv2)
            if self._haar_cascade is None:
                raise RecognitionError(
                    "No face detection backend available. OpenCV Haar cascade could not be loaded."
                )

        self._embedder = self._load_embedder()

    @property
    def detector_name(self) -> str:
        """Return the name of the active face detector."""
        return "mediapipe" if self._mp_detector is not None else "opencv_haar"

    def _load_embedder(self) -> Any | None:
        """Load the ONNX embedding model if provided."""
        if not self._model_path:
            return None
        model = Path(self._model_path).expanduser().resolve()
        if not model.exists():
            return None
        try:
            return self._cv2.dnn.readNetFromONNX(str(model))
        except Exception:
            return None

    def _generate_embedding(self, face_crop: Any) -> list[float]:
        """Generate a face embedding from a face crop image.

        If an ONNX model is loaded, treat it as a FaceNet-style network:
        resize the crop to 160x160, normalize, forward-pass, L2-normalize.
        Otherwise, fall back to float-hash histogram embedding.
        """
        if self._embedder is not None:
            try:
                blob = self._cv2.dnn.blobFromImage(
                    face_crop,
                    scalefactor=1.0 / 255.0,
                    size=(160, 160),
                    mean=(0, 0, 0),
                    swapRB=True,
                    crop=False,
                )
                self._embedder.setInput(blob)
                output = self._embedder.forward()
                vec = output.flatten().tolist()
                norm = math.sqrt(sum(v * v for v in vec)) or 1.0
                return [v / norm for v in vec]
            except Exception:
                pass

        # Fallback: pixel-histogram-based embedding (deterministic, repeatable)
        try:
            resized = self._cv2.resize(face_crop, (64, 64))
            gray = self._cv2.cvtColor(resized, self._cv2.COLOR_BGR2GRAY)
            hist = self._cv2.calcHist([gray], [0], None, [self._embedding_size], [0, 256])
            hist = hist.flatten()
            norm = self._np.linalg.norm(hist) or 1.0
            return (hist / norm).tolist()
        except Exception as exc:
            raise RecognitionError(f"Could not generate face embedding: {exc}") from exc

    def _detect_mediapipe(self, image_bgr: Any, image_rgb: Any) -> list[tuple[int, int, int, int]]:
        """Detect faces using MediaPipe. Returns list of (x, y, w, h)."""
        height, width = image_rgb.shape[:2]
        results = self._mp_detector.process(image_rgb)

        boxes: list[tuple[int, int, int, int]] = []
        if not results.detections:
            return boxes

        for detection in results.detections:
            bbox = detection.location_data.relative_bounding_box
            x = max(0, int(bbox.xmin * width))
            y = max(0, int(bbox.ymin * height))
            w = min(width - x, int(bbox.width * width))
            h = min(height - y, int(bbox.height * height))
            if w > 0 and h > 0:
                boxes.append((x, y, w, h))
        return boxes

    def _detect_haar(self, image_bgr: Any) -> list[tuple[int, int, int, int]]:
        """Detect faces using OpenCV Haar cascade. Returns list of (x, y, w, h)."""
        gray = self._cv2.cvtColor(image_bgr, self._cv2.COLOR_BGR2GRAY)
        gray = self._cv2.equalizeHist(gray)
        detections = self._haar_cascade.detectMultiScale(
            gray,
            scaleFactor=1.05,
            minNeighbors=3,
            minSize=(80, 80),
        )
        if len(detections) == 0:
            return []
        return [(int(x), int(y), int(w), int(h)) for (x, y, w, h) in detections]

    def detect_and_encode(self, image_path: Path) -> list[EncodedFace]:
        """Detect faces and generate embeddings."""
        resolved = image_path.expanduser().resolve()
        if not resolved.exists():
            raise RecognitionError(f"Image file does not exist: {resolved}")

        image_bgr = self._cv2.imread(str(resolved))
        if image_bgr is None:
            raise RecognitionError(f"Could not read image file: {resolved}")

        # Use MediaPipe if available, otherwise Haar cascade.
        if self._mp_detector is not None:
            image_rgb = self._cv2.cvtColor(image_bgr, self._cv2.COLOR_BGR2RGB)
            raw_boxes = self._detect_mediapipe(image_bgr, image_rgb)
        else:
            raw_boxes = self._detect_haar(image_bgr)

        faces: list[EncodedFace] = []
        for x, y, w, h in raw_boxes:
            face_box = FaceBoundingBox(
                top=y,
                right=x + w,
                bottom=y + h,
                left=x,
            )
            face_crop = image_bgr[y : y + h, x : x + w]
            encoding = self._generate_embedding(face_crop)
            faces.append(EncodedFace(bounding_box=face_box, encoding=encoding))

        return faces

    def close(self) -> None:
        """Release detector resources."""
        if self._mp_detector is not None:
            try:
                self._mp_detector.close()
            except Exception:
                pass


def build_recognition_backend(config: dict[str, Any]) -> MediaPipeOpenCVBackend:
    """Build the configured recognition backend."""
    recognition_config = config.get("recognition", {})
    return MediaPipeOpenCVBackend(
        model_path=recognition_config.get("model_path"),
        min_detection_confidence=float(recognition_config.get("min_detection_confidence", 0.5)),
        embedding_size=int(recognition_config.get("embedding_size", 128)),
    )
