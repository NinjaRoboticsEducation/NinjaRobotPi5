"""Renderer helpers for pi5disp."""

from __future__ import annotations

from typing import List, Tuple

import numpy as np


class ColorConverter:
    """Convert RGB888 images into display-native RGB565 bytes."""

    def __init__(self) -> None:
        self._r_lut = (np.arange(256, dtype=np.uint16) >> 3) << 11
        self._g_lut = (np.arange(256, dtype=np.uint16) >> 2) << 5
        self._b_lut = np.arange(256, dtype=np.uint16) >> 3

    def rgb_to_rgb565_bytes(self, rgb_array: np.ndarray) -> bytes:
        """Convert an RGB numpy array to big-endian RGB565 byte string."""
        red = self._r_lut[rgb_array[:, :, 0]]
        green = self._g_lut[rgb_array[:, :, 1]]
        blue = self._b_lut[rgb_array[:, :, 2]]
        rgb565 = red | green | blue
        return rgb565.astype(">u2").tobytes()


class RegionOptimizer:
    """Utilities for clamping and merging partial update regions."""

    @staticmethod
    def clamp_region(
        region: Tuple[int, int, int, int],
        width: int,
        height: int,
    ) -> Tuple[int, int, int, int]:
        """Clamp a region's coordinates to display boundaries."""
        return (
            max(0, region[0]),
            max(0, region[1]),
            min(width, region[2]),
            min(height, region[3]),
        )

    @staticmethod
    def merge_regions(
        regions: List[Tuple[int, int, int, int]],
        max_regions: int = 8,
        merge_threshold: int = 50,
    ) -> List[Tuple[int, int, int, int]]:
        """Merge overlapping or nearby regions."""
        if len(regions) <= 1:
            return regions

        valid = [
            region
            for region in regions
            if region and region[2] > region[0] and region[3] > region[1]
        ]
        if not valid:
            return []

        sorted_regions = sorted(
            valid,
            key=lambda region: (region[2] - region[0]) * (region[3] - region[1]),
        )
        merged: List[Tuple[int, int, int, int]] = []

        while sorted_regions:
            current = sorted_regions.pop(0)
            was_merged = False
            for index, existing in enumerate(merged):
                if RegionOptimizer._should_merge(current, existing, merge_threshold):
                    merged[index] = RegionOptimizer._merge_two(current, existing)
                    was_merged = True
                    break
            if not was_merged:
                merged.append(current)

        while len(merged) > max_regions:
            min_area_increase = float("inf")
            best_pair = (0, 1)
            for i in range(len(merged)):
                for j in range(i + 1, len(merged)):
                    region_a, region_b = merged[i], merged[j]
                    merged_region = RegionOptimizer._merge_two(region_a, region_b)
                    area_increase = (
                        (merged_region[2] - merged_region[0])
                        * (merged_region[3] - merged_region[1])
                        - (region_a[2] - region_a[0]) * (region_a[3] - region_a[1])
                        - (region_b[2] - region_b[0]) * (region_b[3] - region_b[1])
                    )
                    if area_increase < min_area_increase:
                        min_area_increase = area_increase
                        best_pair = (i, j)

            high_index, low_index = max(best_pair), min(best_pair)
            merged_region = RegionOptimizer._merge_two(merged[high_index], merged[low_index])
            merged.pop(high_index)
            merged.pop(low_index)
            merged.append(merged_region)

        return merged

    @staticmethod
    def _should_merge(
        region_a: Tuple[int, int, int, int],
        region_b: Tuple[int, int, int, int],
        merge_threshold: int,
    ) -> bool:
        """Return True if two regions overlap or are nearby."""
        return not (
            region_a[2] + merge_threshold < region_b[0]
            or region_b[2] + merge_threshold < region_a[0]
            or region_a[3] + merge_threshold < region_b[1]
            or region_b[3] + merge_threshold < region_a[1]
        )

    @staticmethod
    def _merge_two(
        region_a: Tuple[int, int, int, int],
        region_b: Tuple[int, int, int, int],
    ) -> Tuple[int, int, int, int]:
        """Merge two regions into one bounding box."""
        return (
            min(region_a[0], region_b[0]),
            min(region_a[1], region_b[1]),
            max(region_a[2], region_b[2]),
            max(region_a[3], region_b[3]),
        )
