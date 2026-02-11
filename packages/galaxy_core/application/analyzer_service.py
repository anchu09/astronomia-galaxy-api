from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from packages.galaxy_core.domain.models import SegmentationResult
from packages.galaxy_core.infrastructure.synthetic import normalize_image


@dataclass
class BasicGalaxyAnalyzer:
    threshold_quantile: float = 0.75

    def segment_galaxy(self, image: np.ndarray) -> SegmentationResult:
        normalized = normalize_image(image)
        threshold = float(np.quantile(normalized, self.threshold_quantile))
        mask = (normalized >= threshold).astype(np.uint8)
        metadata: dict[str, float | int | str] = {
            "threshold": threshold,
            "mask_pixels": int(mask.sum()),
            "algorithm": "quantile_threshold",
        }
        return SegmentationResult(mask=mask, metadata=metadata)

    def measure_basic(self, image: np.ndarray, mask: np.ndarray) -> dict[str, float]:
        if image.shape != mask.shape:
            raise ValueError("image and mask must have the same shape")

        indices = np.argwhere(mask > 0)
        if indices.size == 0:
            return {
                "area_pixels": 0.0,
                "centroid_x": 0.0,
                "centroid_y": 0.0,
                "ellipticity": 0.0,
                "mean_intensity": 0.0,
            }

        y_coords = indices[:, 0].astype(np.float64)
        x_coords = indices[:, 1].astype(np.float64)
        centroid_y = float(y_coords.mean())
        centroid_x = float(x_coords.mean())

        x_std = float(x_coords.std() + 1e-9)
        y_std = float(y_coords.std() + 1e-9)
        major = max(x_std, y_std)
        minor = min(x_std, y_std)
        ellipticity = float(1.0 - (minor / major))
        mean_intensity = float(np.mean(image[mask > 0]))

        return {
            "area_pixels": float(indices.shape[0]),
            "centroid_x": centroid_x,
            "centroid_y": centroid_y,
            "ellipticity": ellipticity,
            "mean_intensity": mean_intensity,
        }

    def morphology_summary(self, measurements: dict[str, float]) -> str:
        area = measurements.get("area_pixels", 0.0)
        ellipticity = measurements.get("ellipticity", 0.0)
        intensity = measurements.get("mean_intensity", 0.0)
        return (
            f"Detected galaxy-like structure with area ~{area:.0f} pixels, "
            f"ellipticity {ellipticity:.2f}, and mean intensity {intensity:.2f}."
        )
