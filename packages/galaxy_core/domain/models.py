from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

import numpy as np


@dataclass(frozen=True)
class SegmentationResult:
    mask: np.ndarray
    metadata: dict[str, float | int | str]


class GalaxyAnalyzer(Protocol):
    def segment_galaxy(self, image: np.ndarray) -> SegmentationResult: ...

    def measure_basic(self, image: np.ndarray, mask: np.ndarray) -> dict[str, float]: ...

    def morphology_summary(self, measurements: dict[str, float]) -> str: ...
