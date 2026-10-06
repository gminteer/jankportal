import asyncio
import math
from enum import Enum
from typing import TYPE_CHECKING, Any

import gi
from evdev import ecodes

if TYPE_CHECKING:
    from evdev import InputEvent

    from jankportal.app import JankWindow

gi.require_version("Gtk", "4.0")
gi.require_version("WebKit", "6.0")
from gi.repository import GLib, Gtk, WebKit  # noqa: E402


class Horizontal(Enum):
    LEFT = -1
    HCENTER = 0
    RIGHT = 1


class Vertical(Enum):
    UP = -1
    VCENTER = 0
    DOWN = 1


DirectionMap = {
    Horizontal.LEFT: Gtk.DirectionType.LEFT,
    Horizontal.RIGHT: Gtk.DirectionType.RIGHT,
    Vertical.UP: Gtk.DirectionType.UP,
    Vertical.DOWN: Gtk.DirectionType.DOWN,
}


def flatten(value: float):
    """Flatten normalized float to [-1, 0, 1]"""
    return math.floor(value) if value < 0 else math.ceil(value) if value > 0 else 0


class AxisInfo:
    def __init__(self, min: int, max: int, deadzone: float):
        self._min = min
        self._max = max
        self._center = None
        self._range = None
        self._deadzone = deadzone

    @property
    def center(self):
        if self._center is None:
            self._center = self._min + self._max // 2
        return self._center

    @property
    def range(self):
        if self._range is None:
            self._range = self._max - self.center
        return self._range

    def normalize(self, value: int) -> float:
        normalized = (value - self.center) / self.range
        return (
            normalized
            if (normalized < -self._deadzone) or (normalized > self._deadzone)
            else 0
        )


class Direction:
    DEADZONE = 0.6
    REPEAT_RATE = 0.5

    def __init__(
        self,
        x_axis: AxisInfo,
        y_axis: AxisInfo,
        window: JankWindow,
    ):
        self._x_val = Horizontal(0)
        self._y_val = Vertical(0)
        self._x_axis = x_axis
        self._y_axis = y_axis
        self._window = window

    async def _repeat_move(self, direction: Horizontal | Vertical):
        direction_val = (
            self._x_val if isinstance(direction, Horizontal) else self._y_val
        )
        while direction == direction_val:
            if not self._window.props.focus_visible:
                self._window.props.focus_visible = True
            self._window.emit("move-focus", DirectionMap[direction])
            await asyncio.sleep(self.REPEAT_RATE)

    @property
    def x(self):
        return self._x_val

    @x.setter
    def x(self, value: int):
        """Set x axis direction, start asynchronously sending direction signals
        if x isn't centered"""

        if value not in {item.value for item in Horizontal}:
            raise ValueError(f"Invalid horziontal direction '{value}'")
        if self._x_val != Horizontal(value):
            self._x_val = Horizontal(value)
            if self._x_val == Horizontal.HCENTER:
                self._x_signal.cancel()
                del self._x_signal
                return
            self._x_signal = asyncio.create_task(self._repeat_move(self.x))

    @property
    def y(self):
        return self._y_val

    @y.setter
    def y(self, value: int):
        """Set y axis direction, start asynchronously sending direction signals
        if y isn't centered"""

        if value not in {item.value for item in Vertical}:
            raise ValueError(f"Invalid vertical direction '{value}'")
        if self._y_val != Vertical(value):
            self._y_val = Vertical(value)
            if self._y_val == Vertical.VCENTER:
                self._y_signal.cancel()
                del self._y_signal
                return
            self._y_signal = asyncio.create_task(self._repeat_move(self.y))

    def update(self, event: InputEvent) -> None:
        """Read evdev event and update direction"""

        match event.code:
            case ecodes.ABS_HAT0X:
                self.x = event.value
            case ecodes.ABS_HAT0Y:
                self.y = event.value
            case ecodes.ABS_X:
                self.x = flatten(self._x_axis.normalize(event.value))
            case ecodes.ABS_Y:
                self.y = flatten(self._y_axis.normalize(event.value))
            case _:
                pass


class Scroller:
    STEP = 25
    DEADZONE = 0.1
    REPEAT_RATE = 0.02

    def __init__(self, scroll_axis: AxisInfo):
        self._scroll_val = 0
        self._scroll_axis = scroll_axis
        self._scroll_signal = None

    async def _repeat_signal_gtk(self, scrollable: Gtk.ScrolledWindow):
        while True:
            v_adj = scrollable.props.vadjustment
            position = v_adj.props.value + self._scroll_val
            position = max(v_adj.props.lower, position)
            position = min(v_adj.props.upper, position)
            v_adj.props.value = position
            await asyncio.sleep(self.REPEAT_RATE)

    async def _repeat_signal_webview(self, webview: WebKit.WebView):
        def callback(webview: WebKit.WebView, result: Any):
            # webkit gets grumpy if you don't _finish javascript evals
            try:
                _value = webview.evaluate_javascript_finish(result)
            except GLib.Error as error:
                print(f"Something went wrong :( -- {error.message}")

        while True:
            webview.evaluate_javascript(
                f"window.scrollBy({{top: {self._scroll_val}, behavior: 'smooth'}})",
                length=-1,
                callback=callback,
            )
            await asyncio.sleep(self.REPEAT_RATE)

    def update(self, event: InputEvent, focus: Gtk.Widget):
        self._scroll_val = int(self._scroll_axis.normalize(event.value) * self.STEP)
        if self._scroll_val == 0 and self._scroll_signal:
            self._scroll_signal.cancel()
            self._scroll_signal = None
            return

        if isinstance(focus, WebKit.WebView) and not self._scroll_signal:
            self._scroll_signal = asyncio.create_task(
                self._repeat_signal_webview(focus)
            )
            return

        if (
            scrollable := focus.get_ancestor(Gtk.ScrolledWindow)
        ) and not self._scroll_signal:
            self._scroll_signal = asyncio.create_task(
                self._repeat_signal_gtk(scrollable)
            )
