#
# Copyright (c) 2026, Daily
#
# SPDX-License-Identifier: BSD 2-Clause License
#

"""Shared types for the pipecat-subagents framework."""

from enum import Enum


class TaskStatus(str, Enum):
    """Status of a completed task.

    Inherits from ``str`` so values compare naturally with plain strings
    and serialize without extra handling.

    Parameters:
        COMPLETED: The task finished successfully.
        CANCELLED: The task was cancelled by the requester.
        FAILED: The task failed due to a logical/business error.
        ERROR: The task encountered an unexpected runtime error.
    """

    COMPLETED = "completed"
    CANCELLED = "cancelled"
    FAILED = "failed"
    ERROR = "error"
