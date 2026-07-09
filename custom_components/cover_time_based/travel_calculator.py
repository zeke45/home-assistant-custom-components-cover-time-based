"""Time-based travel position calculator (no Home Assistant dependency)."""
import time


class TravelStatus:
    DIRECTION_UP = "up"
    DIRECTION_DOWN = "down"
    DIRECTION_NONE = "none"


class TravelCalculator:
    """Compute the current cover position based on elapsed travel time."""

    def __init__(self, travel_time_down: int, travel_time_up: int) -> None:
        self._travel_time_down: int = max(travel_time_down, 1)
        self._travel_time_up: int = max(travel_time_up, 1)
        self._position: int = 100
        self._target_position: int = 100
        # Monotonic timestamp (seconds, float) — immune to wall-clock jumps
        # (NTP resync, DST change) while a travel is in progress.
        self._travel_started_at: float | None = None
        self._travel_direction: str = TravelStatus.DIRECTION_NONE

    @property
    def travel_direction(self) -> str:
        return self._travel_direction

    def set_position(self, position: int) -> None:
        self._position = position
        self._target_position = position

    def current_position(self) -> int:
        if self._travel_started_at is None:
            return self._position
        elapsed = time.monotonic() - self._travel_started_at
        if self._travel_direction == TravelStatus.DIRECTION_UP:
            diff = 100.0 * elapsed / self._travel_time_up
            pos = min(self._position + diff, 100.0)
        else:
            diff = 100.0 * elapsed / self._travel_time_down
            pos = max(self._position - diff, 0.0)
        return int(round(pos))

    def start_travel(self, target_position: int) -> None:
        self._position = self.current_position()
        self._target_position = target_position
        self._travel_started_at = time.monotonic()
        if target_position > self._position:
            self._travel_direction = TravelStatus.DIRECTION_UP
        else:
            self._travel_direction = TravelStatus.DIRECTION_DOWN

    def start_travel_up(self) -> None:
        self.start_travel(100)

    def start_travel_down(self) -> None:
        self.start_travel(0)

    def stop(self) -> None:
        self._position = self.current_position()
        self._target_position = self._position
        self._travel_started_at = None
        self._travel_direction = TravelStatus.DIRECTION_NONE

    def position_reached(self) -> bool:
        if self._travel_started_at is None:
            return True
        current = self.current_position()
        if self._travel_direction == TravelStatus.DIRECTION_UP:
            return current >= self._target_position
        return current <= self._target_position

    def is_traveling(self) -> bool:
        return self._travel_started_at is not None and not self.position_reached()

    def is_closed(self) -> bool:
        return self.current_position() == 0

