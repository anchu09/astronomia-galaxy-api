from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image

from packages.galaxy_agent.models import Artifact


class ArtifactStore:
    def __init__(self, base_dir: str = "artifacts") -> None:
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _request_dir(self, request_id: str) -> Path:
        path = self.base_dir / request_id
        path.mkdir(parents=True, exist_ok=True)
        return path

    def save_mask(self, request_id: str, mask: np.ndarray) -> Artifact:
        path = self._request_dir(request_id) / "mask.png"
        img = Image.fromarray((mask.astype(np.uint8) * 255), mode="L")
        img.save(path)
        return Artifact(type="mask", path=self._relative(path))

    def save_report(self, request_id: str, content: str) -> Artifact:
        path = self._request_dir(request_id) / "report.txt"
        path.write_text(content, encoding="utf-8")
        return Artifact(type="report", path=self._relative(path))

    def save_measurements(self, request_id: str, payload: dict[str, Any]) -> Artifact:
        path = self._request_dir(request_id) / "measurements.json"
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return Artifact(type="report", path=self._relative(path))

    def save_image(self, request_id: str, image_bytes: bytes) -> str:
        """Save downloaded image bytes to request dir; return path for load_image."""
        path = self._request_dir(request_id) / "image.jpg"
        path.write_bytes(image_bytes)
        return self._relative(path)

    def _relative(self, path: Path) -> str:
        return path.as_posix()
