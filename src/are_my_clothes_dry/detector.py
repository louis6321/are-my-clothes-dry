"""Detect dryer cycles from a stream of power readings."""

from dataclasses import dataclass


@dataclass(frozen=True)
class CycleStarted:
    pass


@dataclass(frozen=True)
class CycleFinished:
    duration_s: float


Event = CycleStarted | CycleFinished


class DryerDetector:
    """State machine fed one power reading at a time.

    A run starts on the first reading above `threshold_w`, emitting `CycleStarted`.
    It ends after `idle_after_s` of readings at or below the threshold, emitting
    `CycleFinished`. Every `CycleStarted` is followed by a `CycleFinished`.
    """

    def __init__(self, threshold_w: float = 10, idle_after_s: float = 60) -> None:
        self.threshold_w = threshold_w
        self.idle_after_s = idle_after_s
        self._run_started: float | None = None
        self._below_since: float | None = None

    def update(self, now: float, watts: float) -> Event | None:
        above = watts > self.threshold_w

        if self._run_started is None:
            if not above:
                return None
            self._run_started = now
            return CycleStarted()

        if above:
            self._below_since = None
            return None

        if self._below_since is None:
            self._below_since = now
        if now - self._below_since < self.idle_after_s:
            return None

        duration_s = self._below_since - self._run_started
        self._run_started = None
        self._below_since = None
        return CycleFinished(duration_s)
