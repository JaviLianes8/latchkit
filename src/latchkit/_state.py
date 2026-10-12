"""The three states every one-shot primitive moves through, once."""

from __future__ import annotations

__all__ = ["BROKEN", "OPEN", "PENDING", "STATE_NAMES"]

PENDING = 0
"""Not opened and not aborted: waiters block."""

OPEN = 1
"""Opened for good: every current and future wait returns ``True``."""

BROKEN = 2
"""Aborted for good: every current and future wait raises ``BrokenLatchError``."""

STATE_NAMES = {PENDING: "pending", OPEN: "open", BROKEN: "broken"}
