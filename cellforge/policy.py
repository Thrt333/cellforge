"""Hardware-independent connection policy for the 1.0.0 prototype.

Decisions are intents, not USB operations. A module adapter must supply fresh
observations and explicitly report completion; importing this module performs
no I/O. All times are seconds from one monotonic clock.
"""
from dataclasses import dataclass
import math
from typing import Optional


@dataclass(frozen=True)
class Observation:
    # None means unknown, never false. 'absent' must be confirmed by the adapter.
    attached: Optional[bool] = None
    usb: str = "unknown"  # configured, suspended, disconnected, unknown
    sim_ready: Optional[bool] = None
    radio: str = "unknown"  # lte, legacy, none, unknown
    strong_signal: Optional[bool] = None
    host_ok: Optional[bool] = None
    host_seen: Optional[float] = None
    uplink_ok: Optional[bool] = None
    uplink_seen: Optional[float] = None
    wakeup_armed: Optional[bool] = None
    wakeup_supported: bool = False


@dataclass(frozen=True)
class Settings:
    evidence_ttl: float = 30
    check_grace: float = 5
    action_timeout: float = 5
    retry_delay: float = 15
    max_attempts: int = 3

    def __post_init__(self):
        if (not all(math.isfinite(x) for x in (self.evidence_ttl, self.check_grace,
                                              self.action_timeout, self.retry_delay))
                or min(self.evidence_ttl, self.action_timeout, self.retry_delay) <= 0
                or self.check_grace < 0 or self.max_attempts < 1):
            raise ValueError("Invalid policy timing or attempt limit")


@dataclass(frozen=True)
class Intent:
    token: int
    kind: str
    deadline: float


@dataclass(frozen=True)
class Decision:
    state: str
    led: Optional[str]
    reason: str
    intent: Optional[Intent] = None
    next_attempt: Optional[float] = None


class Controller:
    def __init__(self, settings=Settings()):
        self.settings = settings
        self.pending = None
        self.attempts = 0
        self.next_attempt = 0.0
        self.sequence = 0
        self.last_tick = None
        self.last_healthy = None
        self.check_started = None
        self.evidence_cutoff = 0.0

    def _clock(self, now):
        if not math.isfinite(now) or (self.last_tick is not None and now < self.last_tick):
            raise ValueError("Monotonic time moved backwards")
        self.last_tick = now

    def _fresh(self, ok, timestamp, now):
        return (ok is True and timestamp is not None
                and timestamp >= self.evidence_cutoff
                and 0 <= now - timestamp <= self.settings.evidence_ttl)

    @staticmethod
    def _radio_led(obs):
        if obs.sim_ready is False:
            return "red_solid"
        if obs.sim_ready is not True:
            return None
        if obs.radio == "none":
            return "red_blink"
        color = {"lte": "green", "legacy": "yellow"}.get(obs.radio)
        if color is None or obs.strong_signal is None:
            return None
        return color + ("_solid" if obs.strong_signal else "_blink")

    def _cancel(self):
        self.pending = None
        self.check_started = None

    def tick(self, obs, now):
        self._clock(now)
        radio_led = self._radio_led(obs)
        if obs.attached is False:
            self._cancel()
            self.attempts, self.next_attempt = 0, 0.0
            self.last_healthy = None
            self.evidence_cutoff = now
            return Decision("detached", radio_led, "confirmed_detach")
        if obs.sim_ready is False or (obs.sim_ready is True and obs.radio == "none"):
            self._cancel()
            self.last_healthy = None
            self.evidence_cutoff = now
            return Decision("radio_fault", radio_led, "sim_or_radio_unavailable")

        healthy = (obs.attached is True and obs.usb == "configured"
                   and obs.sim_ready is True and obs.radio in ("lte", "legacy")
                   and self._fresh(obs.host_ok, obs.host_seen, now)
                   and self._fresh(obs.uplink_ok, obs.uplink_seen, now))
        if healthy:
            self._cancel()
            self.attempts, self.next_attempt = 0, 0.0
            self.last_healthy = now
            return Decision("active", "blue_solid", "fresh_host_and_uplink_evidence")

        # Unknown attachment is not a fault and must never trigger recovery.
        if obs.attached is not True:
            self._cancel()
            self.last_healthy = None
            return Decision("unknown", None, "attachment_not_observable")

        if self.pending is not None:
            if now < self.pending.deadline:
                return Decision("recovering", "blue_blink", "awaiting_wakeup_result")
            self.pending = None
            self.next_attempt = now + self.settings.retry_delay
            self.last_healthy = None
            return Decision("backoff", radio_led, "wakeup_timeout",
                            next_attempt=self.next_attempt)

        if obs.usb == "suspended":
            self.last_healthy = None
            self.evidence_cutoff = now
            if not obs.wakeup_supported or obs.wakeup_armed is not True:
                return Decision("limited", radio_led, "wakeup_unavailable_or_not_armed")
            if self.attempts >= self.settings.max_attempts:
                return Decision("limited", radio_led, "attempt_budget_exhausted")
            if now < self.next_attempt:
                return Decision("backoff", radio_led, "retry_delay",
                                next_attempt=self.next_attempt)
            self.sequence += 1
            self.attempts += 1
            self.pending = Intent(self.sequence, "request_usb_wakeup",
                                  now + self.settings.action_timeout)
            return Decision("recovering", "blue_blink", "confirmed_suspend", self.pending)

        # A failed probe does not authorize re-enumeration, PDP reset or reboot.
        if obs.host_ok is False or obs.uplink_ok is False or obs.usb == "disconnected":
            self.last_healthy = None
            self.evidence_cutoff = now
            self.check_started = None
            return Decision("limited", radio_led, "communication_failed_no_destructive_adapter")

        if self.check_started is None:
            self.check_started = now
        grace = (self.last_healthy is not None
                 and now - self.check_started < self.settings.check_grace)
        return Decision("checking", "blue_solid" if grace else None,
                        "evidence_expired_or_missing")

    def complete(self, token, now):
        """Record dispatch completion, not connectivity success.

        Even a successful wakeup request must be followed by fresh host/uplink
        evidence. Late/duplicate completions cannot alter another action.
        """
        self._clock(now)
        if self.pending is None or self.pending.token != token:
            return False
        self.pending = None
        self.next_attempt = now + self.settings.retry_delay
        self.last_healthy = None
        return True


class Traffic:
    """Accumulate one adapter's user-oriented cellular byte counters.

    A missing/reset/replaced sample invalidates the rate. A gap can still add
    known nonnegative bytes for the same counter epoch, but never invents speed.
    """
    def __init__(self):
        self.totals = [0, 0]
        self.previous = None
        self.gap = False
        self.last_time = None
        self.discontinuities = 0

    def sample(self, now, epoch=None, upload=None, download=None):
        if self.last_time is not None and now <= self.last_time:
            raise ValueError("Traffic sample time must strictly increase")
        self.last_time = now
        rates = [None, None]
        quality = "missing"
        if epoch is not None and upload is not None and download is not None:
            if (type(upload) is not int or type(download) is not int
                    or upload < 0 or download < 0):
                raise ValueError("Byte counters must be nonnegative integers")
            current = [upload, download]
            quality = "limited"
            if self.previous is not None:
                old_time, old_epoch, old = self.previous
                if epoch == old_epoch and all(x >= y for x, y in zip(current, old)):
                    delta = [x - y for x, y in zip(current, old)]
                    self.totals = [x + y for x, y in zip(self.totals, delta)]
                    if not self.gap:
                        rates = [x / (now - old_time) for x in delta]
                        quality = "available"
                else:
                    self.discontinuities += 1
            self.previous = (now, epoch, current)
            self.gap = False
        else:
            self.gap = True
        return {"quality": quality, "upload_bytes": self.totals[0],
                "download_bytes": self.totals[1],
                "upload_bytes_per_second": rates[0],
                "download_bytes_per_second": rates[1],
                "discontinuities": self.discontinuities}
