from __future__ import annotations

from dataclasses import dataclass

from .models import Act, ActEvent


class TranscriptFrozenError(RuntimeError):
    """Raised when an act is appended after the transcript is frozen."""


@dataclass(frozen=True)
class FrozenTranscript:
    version: int
    events: tuple[ActEvent, ...]


class Transcript:
    def __init__(self) -> None:
        self._events: list[ActEvent] = []
        self._frozen = False

    @property
    def version(self) -> int:
        return len(self._events)

    def append(self, act: Act, *, seen_through_event_id: int) -> ActEvent:
        if self._frozen:
            raise TranscriptFrozenError("Transcript is frozen")
        if seen_through_event_id < 0 or seen_through_event_id > self.version:
            raise ValueError(
                "seen_through_event_id must reference an existing transcript version"
            )
        # a core can only reply to something it already saw
        if act.reply_to is not None and not 1 <= act.reply_to <= seen_through_event_id:
            raise ValueError(
                "reply_to must reference an event visible to the responding core"
            )

        event = ActEvent(
            id=self.version + 1,
            seen_through_event_id=seen_through_event_id,
            act=act,
        )
        self._events.append(event)
        return event

    def snapshot(self) -> FrozenTranscript:
        return FrozenTranscript(self.version, tuple(self._events))

    def freeze(self) -> FrozenTranscript:
        self._frozen = True
        return self.snapshot()
