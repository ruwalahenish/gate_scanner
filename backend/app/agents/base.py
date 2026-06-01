"""
agents/base.py
===============
Abstract base class for all GATE pipeline agents.
Provides shared logging and a uniform repr.
"""

from __future__ import annotations

import logging
from abc import ABC


class BaseAgent(ABC):
    def __init__(self):
        self._log = logging.getLogger(f"gate.agent.{type(self).__name__}")

    def __repr__(self) -> str:
        return f"<{type(self).__name__}>"
