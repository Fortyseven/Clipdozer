"""Time formatting utilities.

Currently only provides `format_time` which formats seconds as mm:ss.mmm.
Future additions might include SMPTE formatting, frame<->time conversions, etc.
"""

from __future__ import annotations

__all__ = ["format_time"]


def format_time(seconds: float) -> str:
    """Return a human-friendly timestamp mm:ss.mmm for UI labels.

    Uses ROUND_HALF_UP semantics for milliseconds to avoid Python's bankers rounding
    edge cases (e.g., 1.2345 -> 1.235). Accepts negative (clamps display to 0).
    """
    if seconds < 0:
        seconds = 0.0
    from decimal import Decimal, ROUND_HALF_UP

    ms_total = int(
        (Decimal(str(seconds)) * Decimal(1000)).to_integral_value(
            rounding=ROUND_HALF_UP
        )
    )
    m, rem = divmod(ms_total, 60000)
    s, ms = divmod(rem, 1000)
    return f"{m:02d}:{s:02d}.{ms:03d}"  # mm:ss.mmm
