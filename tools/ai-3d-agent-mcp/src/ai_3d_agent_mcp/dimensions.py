from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass
class TargetDimensions:
    """Target bounding box in millimetres (print orientation)."""

    width_mm: float
    depth_mm: float
    height_mm: float
    scale_mode: str = "fit_bbox"  # fit_bbox | match_longest | match_height

    def __post_init__(self) -> None:
        for name, value in (
            ("width_mm", self.width_mm),
            ("depth_mm", self.depth_mm),
            ("height_mm", self.height_mm),
        ):
            if value is None or float(value) <= 0:
                raise ValueError(f"{name} must be a positive number (mm)")
        self.width_mm = float(self.width_mm)
        self.depth_mm = float(self.depth_mm)
        self.height_mm = float(self.height_mm)
        if self.scale_mode not in {"fit_bbox", "match_longest", "match_height"}:
            raise ValueError("scale_mode must be fit_bbox, match_longest, or match_height")

    @property
    def volume_mm3(self) -> float:
        return self.width_mm * self.depth_mm * self.height_mm

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)

    def fits_bed(self, bed_mm: list[float], margin_mm: float = 2.0) -> tuple[bool, str]:
        bx, by, bz = bed_mm
        ok = (
            self.width_mm <= bx - margin_mm
            and self.depth_mm <= by - margin_mm
            and self.height_mm <= bz - margin_mm
        )
        msg = (
            f"target {self.width_mm:.1f}×{self.depth_mm:.1f}×{self.height_mm:.1f} mm "
            f"vs bed {bx:.0f}×{by:.0f}×{bz:.0f} mm (margin {margin_mm} mm)"
        )
        return ok, msg


def parse_dimensions(
    width_mm: float,
    depth_mm: float,
    height_mm: float,
    scale_mode: str = "fit_bbox",
) -> TargetDimensions:
    return TargetDimensions(
        width_mm=width_mm,
        depth_mm=depth_mm,
        height_mm=height_mm,
        scale_mode=scale_mode,
    )


def missing_dimensions_prompt(category: str) -> dict[str, Any]:
    hints = {
        "figurine": "Typical desk figurine: 40–80 mm tall. Give W×D×H of the final print.",
        "hook": "Wall hook: plate size + protrusion. Example: 40×20×60 mm (W×D×H).",
        "sign": "Sign plate: width × thickness × height. Example: 120×3×60 mm.",
        "functional": "Give the critical bounding box the part must fit inside.",
        "other": "Approximate final print size in millimetres (W×D×H).",
    }
    return {
        "needs_dimensions": True,
        "message": (
            "Dimensional accuracy is required. Provide approximate width_mm, depth_mm, "
            f"and height_mm before generation. Hint: {hints.get(category, hints['other'])}"
        ),
        "fields": ["width_mm", "depth_mm", "height_mm", "scale_mode"],
        "scale_modes": ["fit_bbox", "match_longest", "match_height"],
    }
