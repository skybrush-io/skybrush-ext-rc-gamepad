from typing import Tuple

__all__ = ("Scaler",)


class Scaler:
    """Class that takes an input range and an output range and processes
    incoming values by clamping them to the input range and then scaling
    them linearly so the lower bound of the input range gets mapped to the
    lower bound of the output range and the upper bound of the input range
    gets mapped to the upper bound of the output range.

    Ranges are inclusive from both ends.
    """

    _low: float
    _high: float
    _out_low: float
    _out_high: float
    _scale: float

    def __init__(
        self,
        in_range: Tuple[float, float],
        out_range: Tuple[float, float],
        invert: bool = False,
    ):
        self._low, self._high = in_range

        if invert:
            self._out_high, self._out_low = out_range
        else:
            self._out_low, self._out_high = out_range

        if self._low != self._high:
            self._scale = (self._out_high - self._out_low) / (self._high - self._low)
        else:
            self._scale = 0.0

    def __call__(self, value: float) -> float:
        if value < self._low:
            return self._out_low
        elif value > self._high:
            return self._out_high
        else:
            return self._out_low + (value - self._low) * self._scale
