# type hints on evdev seem to be broken, oh well...
import asyncio
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, cast

import evdev
import gi
from evdev import ecodes

from .lib import DirectionMap, Horizontal, Vertical

if TYPE_CHECKING:
    from collections.abc import Callable

    from jankportal.app import JankPortalWindow

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("WebKit", "6.0")
from gi.repository import Adw, GLib, Gtk, WebKit  # noqa: E402

BTN_DOWN = 1
BTN_UP = 0
REPEAT_RATE = 0.5
DEADZONE = 0.6
SCROLL_STEP = 25


class AxisInfo:
    def __init__(self, min: int, max: int):
        self._min = min
        self._max = max
        self._center = None
        self._range = None

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


@dataclass
class AnalogInfo:
    x: AxisInfo
    y: AxisInfo
    deadzone: float


class Direction:
    def __init__(self, info: AnalogInfo, move: Callable[[Horizontal | Vertical], None]):
        self._x = Horizontal(0)
        self._y = Vertical(0)
        self.info = info
        self.move = move

    async def _repeat(self, direction: Horizontal | Vertical):
        axis = self._x if isinstance(direction, Horizontal) else self._y
        while direction == axis:
            self.move(direction)
            await asyncio.sleep(REPEAT_RATE)

    @property
    def x(self):
        return self._x

    @x.setter
    def x(self, value: int):
        """Set x axis direction, start asynchronously sending direction signals
        if x isn't centered"""

        if value not in {item.value for item in Horizontal}:
            raise ValueError(f"Invalid horziontal direction '{value}'")
        if self._x != Horizontal(value):
            self._x = Horizontal(value)
            if self._x == Horizontal.HCENTER:
                self._x_signal.cancel()
                del self._x_signal
                return
            self._x_signal = asyncio.create_task(self._repeat(self.x))

    @property
    def y(self):
        return self._y

    @y.setter
    def y(self, value: int):
        """Set y axis direction, start asynchronously sending direction signals
        if y isn't centered"""

        if value not in {item.value for item in Vertical}:
            raise ValueError(f"Invalid vertical direction '{value}'")
        if self._y != Vertical(value):
            self._y = Vertical(value)
            if self._y == Vertical.VCENTER:
                self._y_signal.cancel()
                del self._y_signal
                return
            self._y_signal = asyncio.create_task(self._repeat(self.y))

    def get_analog_direction(self, value: int, center: int, range: int):
        """Convert raw axis information to a [-1, 0, 1] value"""

        normalized = (value - center) / range
        if normalized < -self.info.deadzone:
            return -1
        if normalized > self.info.deadzone:
            return 1
        return 0

    def update(self, event: evdev.InputEvent):
        """Read evdev event and update direction"""

        match event.code:
            case ecodes.ABS_HAT0X:
                self.x = event.value
            case ecodes.ABS_HAT0Y:
                self.y = event.value
            case ecodes.ABS_X:
                x = self.info.x
                self.x = self.get_analog_direction(event.value, x.center, x.range)
            case ecodes.ABS_Y:
                y = self.info.y
                self.y = self.get_analog_direction(event.value, y.center, y.range)
            case _:
                pass


def find_joystick():
    """Loop through input devices until we (probably) find a joystick"""

    paths = evdev.list_devices()  # type: ignore
    for path in paths:
        try:
            device: evdev.InputDevice[str] = evdev.InputDevice(path)
            capabilities = device.capabilities()

            if evdev.ecodes.EV_KEY not in capabilities:
                continue

            key_types = capabilities[ecodes.EV_KEY]
            # if it's got joystick buttons it's probably a joystick, right?
            if ecodes.BTN_JOYSTICK in key_types or ecodes.BTN_GAMEPAD in key_types:
                return device
        except OSError, PermissionError:
            continue
    return None


scroll_amount = 0


async def repeat_scroll(scrollable: Gtk.ScrolledWindow):
    while True:
        v_adj = scrollable.props.vadjustment
        new_amount = v_adj.props.value + scroll_amount
        new_amount = max(v_adj.props.lower, new_amount)
        new_amount = min(v_adj.props.upper, new_amount)
        v_adj.props.value = new_amount
        await asyncio.sleep(0.02)


async def repeat_scroll_webview(webview: WebKit.WebView):
    def callback(webview: WebKit.WebView, result: Any):
        try:
            _value = webview.evaluate_javascript_finish(result)
        except GLib.Error as error:
            print(f"Something went wrong :( -- {error.message}")

    while True:
        webview.evaluate_javascript(
            f"window.scrollBy({{top: {scroll_amount}, behavior: 'smooth'}})",
            length=-1,
            callback=callback,
        )
        await asyncio.sleep(0.02)


async def read_joystick(window: JankPortalWindow):
    """read evdev events from a joystick and duct tape them to GTK4"""

    global scroll_amount

    def move(direction: Horizontal | Vertical):
        if not window.props.focus_visible:
            window.props.focus_visible = True
        window.child_focus(DirectionMap[direction])

    device = find_joystick()
    if device is None:
        return
    window.toast(f"Listening to '{device.name}' at {device.path}")
    dev_cap = dict(device.capabilities().get(ecodes.EV_ABS, []))  # type: ignore
    direction_info = AnalogInfo(
        x=AxisInfo(min=dev_cap[ecodes.ABS_X].min, max=dev_cap[ecodes.ABS_X].max),  # type: ignore
        y=AxisInfo(min=dev_cap[ecodes.ABS_Y].min, max=dev_cap[ecodes.ABS_Y].max),  # type: ignore
        deadzone=DEADZONE,
    )
    scroll = AnalogInfo(
        x=AxisInfo(min=dev_cap[ecodes.ABS_RX].min, max=dev_cap[ecodes.ABS_RX].max),  # type: ignore
        y=AxisInfo(min=dev_cap[ecodes.ABS_RY].min, max=dev_cap[ecodes.ABS_RY].max),  # type: ignore
        deadzone=0.05,
    )
    direction = Direction(direction_info, move)
    scrolling = None

    async for event in device.async_read_loop():  # type: ignore
        event = cast("evdev.InputEvent", event)
        if event.type == ecodes.EV_ABS:
            if event.code in [
                ecodes.ABS_X,
                ecodes.ABS_Y,
                ecodes.ABS_HAT0X,
                ecodes.ABS_HAT0Y,
            ]:
                # X, Y, HAT0X, and HAT0Y = arrow keys
                direction.update(event)
            if event.code == ecodes.ABS_RY:
                # RY = scroll widget
                if not (focus := window.get_focus()):
                    continue

                normalized = (event.value - scroll.y.center) / scroll.y.range
                if normalized < -scroll.deadzone or normalized > scroll.deadzone:
                    scroll_amount = int(SCROLL_STEP * normalized)
                else:
                    if isinstance(scrolling, asyncio.Task):
                        scrolling.cancel()
                        scrolling = None

                if isinstance(focus, WebKit.WebView) and not scrolling:
                    scrolling = asyncio.create_task(repeat_scroll_webview(focus))
                elif (
                    scrollable := focus.get_ancestor(Gtk.ScrolledWindow)
                ) and not scrolling:
                    scrolling = asyncio.create_task(repeat_scroll(scrollable))

        elif event.type == ecodes.EV_KEY and event.value == BTN_DOWN:
            match event.code:
                case ecodes.BTN_SOUTH:
                    # south button = enter
                    if not (focus := window.get_focus()):
                        continue
                    focus.activate()

                case ecodes.BTN_EAST:
                    # east button = escape
                    if not (focus := window.get_focus()):
                        continue
                    if isinstance(focus, Gtk.Text):
                        if not (search := focus.get_ancestor(Gtk.SearchEntry)):
                            continue
                        search.emit("stop-search")
                        continue
                    dialog = focus.get_ancestor(Adw.Dialog)
                    if dialog:
                        dialog.close()

                case ecodes.BTN_NORTH:
                    # north button = focus search entry
                    window.search.grab_focus()

                case ecodes.BTN_TL:
                    # left bumper = shift-tab
                    window.child_focus(Gtk.DirectionType.TAB_BACKWARD)

                case ecodes.BTN_TR:
                    # right bumper = tab
                    window.child_focus(Gtk.DirectionType.TAB_FORWARD)

                case ecodes.BTN_TL2:
                    # left trigger = previous viewstack page
                    if not (current_page := window.stack.get_visible_child()):
                        continue
                    page = window.stack.get_first_child()
                    idx = 0
                    wait_for_last_page = False
                    while page is not None:
                        if page.get_next_sibling() == current_page:
                            if idx == 0:
                                # search results are the first page in the stack
                                # so if the first child's next sibling is a match,
                                # loop to the end instead
                                wait_for_last_page = True
                            else:
                                window.stack.set_visible_child(page)
                                break
                        if page.get_next_sibling() is None and wait_for_last_page:
                            window.stack.set_visible_child(page)
                        idx += 1
                        page = page.get_next_sibling()

                case ecodes.BTN_TR2:
                    # right tigger = next viewstack page
                    if not (page := window.stack.get_visible_child()):
                        continue
                    if not (next_page := page.get_next_sibling()):
                        next_page = window.stack.get_first_child()
                        if not next_page:
                            continue
                        # search results are the first page in the stack
                        next_page = next_page.get_next_sibling()
                        if not next_page:
                            continue
                    window.stack.set_visible_child(next_page)

                case ecodes.BTN_START:
                    # start button = show about dialog
                    window.on_about_clicked(None)

                case _:
                    data = evdev.categorize(event)
                    print(f"Code: {event.code}, Value: {event.value}, Category: {data}")
