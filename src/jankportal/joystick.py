# type hints on evdev seem to be broken, oh well...
import asyncio
from dataclasses import dataclass
from typing import TYPE_CHECKING, cast

import evdev
import gi
from evdev import ecodes

from .lib import DirectionMap, Horizontal, Vertical

if TYPE_CHECKING:
    from collections.abc import Callable

    from jankportal.app import JankPortalWindow

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk  # noqa: E402

BTN_DOWN = 1
BTN_UP = 0
REPEAT_RATE = 0.5
DEADZONE = 0.6


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

        normalized = (value - self.info.x.center) / self.info.x.range
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


async def read_joystick(window: JankPortalWindow):
    def move(direction: Horizontal | Vertical):
        if not window.props.focus_visible:
            window.props.focus_visible = True
        window.child_focus(DirectionMap[direction])

    device = find_joystick()
    if device is None:
        return
    window.toast(f"Listening to '{device.name}' at {device.path}")
    dev_cap = dict(device.capabilities().get(ecodes.EV_ABS, []))  # type: ignore
    info = AnalogInfo(
        x=AxisInfo(min=dev_cap[ecodes.ABS_X].min, max=dev_cap[ecodes.ABS_X].max),  # type: ignore
        y=AxisInfo(min=dev_cap[ecodes.ABS_Y].min, max=dev_cap[ecodes.ABS_Y].max),  # type: ignore
        deadzone=DEADZONE,
    )
    direction = Direction(info, move)
    async for event in device.async_read_loop():  # type: ignore
        event = cast("evdev.InputEvent", event)
        if event.type == ecodes.EV_ABS:
            # X, Y, HAT0X, and HAT0Y = arrow keys
            direction.update(event)
        elif event.type == ecodes.EV_KEY and event.value == BTN_DOWN:
            match event.code:
                case ecodes.BTN_SOUTH:
                    # south button = enter
                    focus = window.get_focus()
                    if focus:
                        focus.activate()
                case ecodes.BTN_EAST:
                    # east button = escape
                    # or at least it would be if i knew how
                case ecodes.BTN_NORTH:
                    # north button = focus search entry
                    window.search.grab_focus()
                case ecodes.BTN_TL:
                    # left bumper = shift-tab
                    window.child_focus(Gtk.DirectionType.TAB_BACKWARD)
                case ecodes.BTN_TR:
                    # right bumper = tab
                    window.child_focus(Gtk.DirectionType.TAB_FORWARD)
                case _:
                    data = evdev.categorize(event)
                    print(f"Code: {event.code}, Value: {event.value}, Category: {data}")
        # data = evdev.categorize(event)
        # print(f"Code: {event.code}, Value: {event.value}, Category: {data}")
