"""Unit tests for renderer helpers."""

from __future__ import annotations

import numpy as np

from pi5disp.core.renderer import ColorConverter, RegionOptimizer


class TestColorConverter:
    """Tests for RGB888 to RGB565 conversion."""

    def setup_method(self) -> None:
        self.converter = ColorConverter()

    def test_pure_red(self) -> None:
        rgb = np.array([[[255, 0, 0]]], dtype=np.uint8)
        assert self.converter.rgb_to_rgb565_bytes(rgb) == bytes.fromhex("f800")

    def test_pure_green(self) -> None:
        rgb = np.array([[[0, 255, 0]]], dtype=np.uint8)
        assert self.converter.rgb_to_rgb565_bytes(rgb) == bytes.fromhex("07e0")

    def test_pure_blue(self) -> None:
        rgb = np.array([[[0, 0, 255]]], dtype=np.uint8)
        assert self.converter.rgb_to_rgb565_bytes(rgb) == bytes.fromhex("001f")

    def test_pure_white(self) -> None:
        rgb = np.array([[[255, 255, 255]]], dtype=np.uint8)
        assert self.converter.rgb_to_rgb565_bytes(rgb) == bytes.fromhex("ffff")

    def test_pure_black(self) -> None:
        rgb = np.array([[[0, 0, 0]]], dtype=np.uint8)
        assert self.converter.rgb_to_rgb565_bytes(rgb) == bytes.fromhex("0000")

    def test_output_size(self) -> None:
        rgb = np.zeros((10, 20, 3), dtype=np.uint8)
        assert len(self.converter.rgb_to_rgb565_bytes(rgb)) == 10 * 20 * 2

    def test_multiple_pixels(self) -> None:
        rgb = np.array([[[255, 0, 0], [0, 255, 0]]], dtype=np.uint8)
        assert self.converter.rgb_to_rgb565_bytes(rgb) == bytes.fromhex("f80007e0")


class TestRegionOptimizer:
    """Tests for region clamping and merging."""

    def test_clamp_within_bounds(self) -> None:
        assert RegionOptimizer.clamp_region((10, 20, 30, 40), 240, 320) == (10, 20, 30, 40)

    def test_clamp_negative_coords(self) -> None:
        assert RegionOptimizer.clamp_region((-5, -10, 30, 40), 240, 320) == (0, 0, 30, 40)

    def test_clamp_exceeds_bounds(self) -> None:
        assert RegionOptimizer.clamp_region((10, 20, 500, 600), 240, 320) == (10, 20, 240, 320)

    def test_merge_empty(self) -> None:
        assert RegionOptimizer.merge_regions([]) == []

    def test_merge_single(self) -> None:
        assert RegionOptimizer.merge_regions([(1, 2, 3, 4)]) == [(1, 2, 3, 4)]

    def test_merge_overlapping(self) -> None:
        merged = RegionOptimizer.merge_regions([(0, 0, 10, 10), (8, 8, 20, 20)])
        assert merged == [(0, 0, 20, 20)]

    def test_merge_distant_regions(self) -> None:
        merged = RegionOptimizer.merge_regions(
            [(0, 0, 10, 10), (200, 200, 210, 210)], merge_threshold=10
        )
        assert len(merged) == 2

    def test_merge_invalid_regions(self) -> None:
        merged = RegionOptimizer.merge_regions([(1, 1, 1, 5), (2, 2, 3, 3)])
        assert merged == [(2, 2, 3, 3)]

    def test_merge_max_regions(self) -> None:
        regions = [(index * 10, 0, index * 10 + 5, 5) for index in range(20)]
        merged = RegionOptimizer.merge_regions(regions, max_regions=4, merge_threshold=0)
        assert len(merged) <= 4
