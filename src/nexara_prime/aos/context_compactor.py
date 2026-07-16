"""Context compactor — reduces context window usage for cost efficiency."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class CompactionStrategy(str, Enum):
    NONE = "none"
    MODERATE = "moderate"
    AGGRESSIVE = "aggressive"


@dataclass
class ContextLevel:
    level: int  # L0-L4
    max_tokens: int
    description: str


LEVELS: dict[int, ContextLevel] = {
    0: ContextLevel(0, 2000, "Mission summary"),
    1: ContextLevel(1, 8000, "Current changeset"),
    2: ContextLevel(2, 24000, "Related modules"),
    3: ContextLevel(3, 64000, "Historical decisions"),
    4: ContextLevel(4, 160000, "Full files"),
}


class ContextCompactor:
    """Manages context levels and compaction strategies."""

    def __init__(self, strategy: CompactionStrategy = CompactionStrategy.MODERATE) -> None:
        self.strategy = strategy
        self._file_reads: dict[str, int] = {}
        self._level = 1

    def should_read(self, path: str) -> bool:
        """Return True if this file hasn't been read yet."""
        if path not in self._file_reads:
            return True
        if self.strategy == CompactionStrategy.NONE:
            return self._file_reads[path] < 3
        if self.strategy == CompactionStrategy.MODERATE:
            return self._file_reads[path] < 2
        return self._file_reads[path] < 1  # aggressive

    def mark_read(self, path: str) -> None:
        self._file_reads[path] = self._file_reads.get(path, 0) + 1

    def available_level(self) -> ContextLevel:
        return LEVELS.get(self._level, LEVELS[2])

    def compact(self, strategy: CompactionStrategy | None = None) -> str:
        if strategy:
            self.strategy = strategy
        unique_files = len(self._file_reads)
        total_reads = sum(self._file_reads.values())
        if total_reads == 0:
            return "no reads yet"
        dedup_pct = (total_reads - unique_files) / total_reads * 100
        if dedup_pct > 50:
            return f"heavy duplication: {dedup_pct:.0f}% re-reads — compact now"
        return f"moderate: {unique_files} unique, {total_reads} total ({dedup_pct:.0f}% dup)"
