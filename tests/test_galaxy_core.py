from __future__ import annotations

import numpy as np

from packages.galaxy_core.analyzer import BasicGalaxyAnalyzer, create_synthetic_image


def test_segment_galaxy_returns_binary_mask() -> None:
    analyzer = BasicGalaxyAnalyzer()
    image = create_synthetic_image()

    result = analyzer.segment_galaxy(image)

    assert result.mask.shape == image.shape
    assert set(np.unique(result.mask)).issubset({0, 1})
    assert result.metadata["algorithm"] == "quantile_threshold"


def test_measure_basic_returns_expected_keys() -> None:
    analyzer = BasicGalaxyAnalyzer()
    image = create_synthetic_image((64, 64))
    mask = analyzer.segment_galaxy(image).mask

    measurements = analyzer.measure_basic(image, mask)

    expected_keys = {
        "area_pixels",
        "centroid_x",
        "centroid_y",
        "ellipticity",
        "mean_intensity",
    }
    assert expected_keys.issubset(measurements.keys())
    assert measurements["area_pixels"] > 0


def test_morphology_summary_is_non_empty() -> None:
    analyzer = BasicGalaxyAnalyzer()
    measurements = {
        "area_pixels": 123.0,
        "ellipticity": 0.3,
        "mean_intensity": 0.7,
    }

    summary = analyzer.morphology_summary(measurements)

    assert "Detected galaxy-like structure" in summary
