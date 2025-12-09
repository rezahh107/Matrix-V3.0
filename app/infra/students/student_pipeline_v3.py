"""Compatibility shim exporting the canonical StudentPipelineV3 implementation."""

from __future__ import annotations

from app.infra.students.pipeline_v3 import StudentPipelineResult, StudentPipelineV3

__all__ = ["StudentPipelineResult", "StudentPipelineV3"]
