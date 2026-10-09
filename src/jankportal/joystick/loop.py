# type: ignore
# type hints on evdev seem to only partially exist, and there
# aren't any for pyudev at all. oh well...

import asyncio
from typing import TYPE_CHECKING, cast

import evdev
import pyudev
from evdev import ecodes
from gi.repository import GLib

from .analog import Axis, Direction, Scroller
from .buttons import read_button

if TYPE_CHECKING:
    from jankportal.window import JankWindow

BTN_DOWN = 1
BTN_UP = 0


def is_joystick(device_node: str):
    DPAD = {ecodes.ABS_HAT0X, ecodes.ABS_HAT0Y}
    LEFT_ANALOG = {ecodes.ABS_X, ecodes.ABS_Y}
    KEYS = {ecodes.BTN_SOUTH, ecodes.BTN_EAST, ecodes.BTN_START}
    try:
        cap = evdev.InputDevice(device_node).capabilities()
        if ecodes.EV_ABS not in cap:
            return False
        abs_set = {tuple[0] for tuple in cap[ecodes.EV_ABS]}
        has_direction = DPAD.issubset(abs_set) or LEFT_ANALOG.issubset(abs_set)
        if ecodes.EV_KEY not in cap:
            return False
        key_set = set(cap[ecodes.EV_KEY])
        has_buttons = KEYS.issubset(key_set)
        return has_direction and has_buttons
    except OSError, FileNotFoundError:
        pass
    return False


class JoystickWrangler:
    def __init__(self, window: JankWindow):
        self.window = window
        self._joystick = None

        context = pyudev.Context()

        for device in context.list_devices(subsystem="input", ID_INPUT_JOYSTICK="1"):
            if (
                device.device_node
                and "event" in device.device_node
                and is_joystick(device.device_node)
            ):
                self._joystick = evdev.InputDevice(device.device_node)
                self._joystick_pump = asyncio.create_task(self._read_joystick())
                return
        self.window.toast("No joysticks detected")
        self._monitor = pyudev.Monitor.from_netlink(context)
        self._monitor.filter_by(subsystem="input")
        self._monitor.start()
        GLib.io_add_watch(
            self._monitor.fileno(),
            GLib.IO_IN,
            self.on_udev_action,
        )

    def on_udev_action(self, source, condition):
        print("event!")
        while True:
            device = self._monitor.poll()
            if not device:
                return
            action = device.action
            match action:
                case "add":
                    if self._joystick:
                        print("ignoring, already have a joystick")
                        return
                    if device.device_node and is_joystick(device.device_node):
                        self._joystick = evdev.InputDevice(device.device_node)
                        self._joystick_pump = asyncio.create_task(self._read_joystick())

                case "remove":
                    if device.device_node == self._joystick.path:
                        self.window.toast(
                            f"Joystick '{self._joystick.name}' disconnected"
                        )
                        self._joystick_pump.cancel()
                        self._joystick_pump = None
                    else:
                        print("ignoring, disconnected device isn't our joystick")

    async def _read_joystick(self):
        """read evdev events from a joystick and duct tape them to GTK4"""
        js = self._joystick
        # build analog helpers
        self.window.toast(f"Listening to '{js.name}' at {js.path}")
        dev_cap = dict(js.capabilities().get(ecodes.EV_ABS, []))  # type: ignore
        analog_x = Axis(
            min=dev_cap[ecodes.ABS_X].min,  # type: ignore
            max=dev_cap[ecodes.ABS_X].max,  # type: ignore
            deadzone=Direction.DEADZONE,
        )
        analog_y = Axis(
            min=dev_cap[ecodes.ABS_Y].min,  # type: ignore
            max=dev_cap[ecodes.ABS_Y].max,  # type: ignore
            deadzone=Direction.DEADZONE,
        )

        scroll = Axis(
            min=dev_cap[ecodes.ABS_RY].min,  # type: ignore
            max=dev_cap[ecodes.ABS_RY].max,  # type: ignore
            deadzone=Scroller.DEADZONE,
        )
        direction = Direction(analog_x, analog_y, self.window)
        scroller = Scroller(scroll)
        try:
            async for event in js.async_read_loop():  # type: ignore
                event = cast("evdev.InputEvent", event)
                if event.type == ecodes.EV_ABS:
                    # analog inputs
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
                        if not (focus := self.window.get_focus()):
                            continue
                        scroller.update(event, focus)

                elif event.type == ecodes.EV_KEY and event.value == BTN_DOWN:
                    # button presses
                    if not (focus := self.window.get_focus()):
                        continue
                    read_button(event, focus, self.window)
        except FileNotFoundError, OSError:
            pass
