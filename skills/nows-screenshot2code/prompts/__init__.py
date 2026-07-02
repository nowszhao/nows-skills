"""Prompt templates for nows-screenshot2code skill."""

from .templates import (
    SYSTEM_PROMPT,
    STACKS,
    StackConfig,
    StackType,
    build_image_prompt,
    build_stack_prompt,
    SELF_REVIEW_PROMPT,
)

__all__ = [
    "SYSTEM_PROMPT",
    "STACKS",
    "StackConfig",
    "StackType",
    "build_image_prompt",
    "build_stack_prompt",
    "SELF_REVIEW_PROMPT",
]
