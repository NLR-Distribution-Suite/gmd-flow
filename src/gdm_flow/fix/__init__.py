"""Violation detection and automated fix engine for GDM distribution systems."""

from .detect import (
    BranchLoadingViolation,
    ViolationReport,
    VoltageViolation,
    detect_violations,
)
from .engine import FixIteration, FixResult, fix_violations
from .strategies import (
    AddCapacitorStrategy,
    AdjustRegulatorTapStrategy,
    FixStrategy,
    ResizeConductorStrategy,
    ResizeTransformerStrategy,
)

__all__ = [
    "AddCapacitorStrategy",
    "AdjustRegulatorTapStrategy",
    "BranchLoadingViolation",
    "FixIteration",
    "FixResult",
    "FixStrategy",
    "ResizeConductorStrategy",
    "ResizeTransformerStrategy",
    "ViolationReport",
    "VoltageViolation",
    "detect_violations",
    "fix_violations",
]
