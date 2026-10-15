"""Handle joystick analog inputs"""

import asyncio
import math
from enum import Enum
from typing import TYPE_CHECKING, Any

import gi
from evdev import ecodes

if TYPE_CHECKING:
    from evdev import InputEvent

    from jankportal.window import JankWindow

gi.require_version("Gtk", "4.0")
gi.require_version("WebKit", "6.0")
gi.require_version("Vte", "3.91")
from gi.repository import GLib, Gtk, Vte, WebKit  # noqa: E402


class Horizontal(Enum):
    LEFT = -1
    HCENTER = 0
    RIGHT = 1


class Vertical(Enum):
    UP = -1
    VCENTER = 0
    DOWN = 1


DIRECTION = Horizontal, Vertical

GtkDirectionMap = {
    Horizontal.LEFT: Gtk.DirectionType.LEFT,
    Horizontal.RIGHT: Gtk.DirectionType.RIGHT,
    Vertical.UP: Gtk.DirectionType.UP,
    Vertical.DOWN: Gtk.DirectionType.DOWN,
}

VteDirectionMap = {
    Horizontal.LEFT: b"\x1b[D",
    Horizontal.RIGHT: b"\x1b[C",
    Vertical.UP: b"\x1b[A",
    Vertical.DOWN: b"\x1b[B",
}


def flatten(value: float):
    """Flatten normalized float to [-1, 0, 1]"""
    return math.floor(value) if value < 0 else math.ceil(value) if value > 0 else 0


class Axis:
    def __init__(self, min: int, max: int, deadzone: float):
        self._min = min
        self._max = max
        self._center = None
        self._range = None
        self._deadzone = deadzone

    @property
    def center(self):
        """Midpoint of analog axis"""
        if self._center is None:
            self._center = self._min + self._max // 2
        return self._center

    @property
    def range(self):
        """Distance from midpoint to extents"""
        if self._range is None:
            self._range = self._max - self.center
        return self._range

    def normalize(self, value: int) -> float:
        """Convert absolute value to float in range [-1, 1], clamp
        to zero if value falls within deadzone"""
        normalized = (value - self.center) / self.range
        if -self._deadzone < normalized < self._deadzone:
            normalized = 0
        return normalized


class Direction:
    DEADZONE = 0.6
    REPEAT_RATE = 0.25

    def __init__(
        self,
        x_axis: Axis,
        y_axis: Axis,
        window: JankWindow,
    ):
        self._axes = x_axis, y_axis
        self._signals: list[None | asyncio.Task[None]] = [None, None]
        self._window = window

    async def _repeat_signal_gtk(self, direction: Horizontal | Vertical):
        while True:
            if not self._window.props.focus_visible:
                self._window.props.focus_visible = True
            self._window.emit("move-focus", GtkDirectionMap[direction])
            await asyncio.sleep(self.REPEAT_RATE)

    async def _repeat_signal_vte(self, direction: Horizontal | Vertical):
        while True:
            self._window.vte.feed_child(VteDirectionMap[direction])
            await asyncio.sleep(self.REPEAT_RATE)

    def update(self, event: InputEvent, focus: Gtk.Widget) -> None:
        """Read evdev event and update direction"""
        x = None
        y = None
        match event.code:
            case ecodes.ABS_HAT0X:
                x = event.value
            case ecodes.ABS_HAT0Y:
                y = event.value
            case ecodes.ABS_X:
                x = flatten(self._axes[0].normalize(event.value))
            case ecodes.ABS_Y:
                y = flatten(self._axes[1].normalize(event.value))
            case _:
                pass

        for i, val in enumerate((x, y)):
            signal = self._signals[i]
            if val == 0:
                if signal:
                    signal.cancel()
                    self._signals[i] = None
                return
            if val in [-1, 1]:
                if not signal:
                    if isinstance(focus, Vte.Terminal):
                        self._signals[i] = asyncio.create_task(
                            self._repeat_signal_vte(DIRECTION[i](val))
                        )
                    else:
                        self._signals[i] = asyncio.create_task(
                            self._repeat_signal_gtk(DIRECTION[i](val))
                        )
                return


class Scroller:
    STEP = 25
    DEADZONE = 0.1
    REPEAT_RATE = 0.02

    def __init__(self, scroll_axis: Axis, window: JankWindow):
        self._scroll_val = 0
        self._scroll_axis = scroll_axis
        self._scroll_signal = None
        self._window = window

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
