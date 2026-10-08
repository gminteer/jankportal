# type hints on evdev seem to be broken, oh well...
from typing import TYPE_CHECKING, cast

import evdev
from evdev import ecodes

from .analog import Axis, Direction, Scroller
from .buttons import read_button

if TYPE_CHECKING:
    from jankportal.window import JankWindow

BTN_DOWN = 1
BTN_UP = 0


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


async def read_joystick(window: JankWindow):
    """read evdev events from a joystick and duct tape them to GTK4"""

    device = find_joystick()
    if device is None:
        return

    # build analog helpers
    window.toast(f"Listening to '{device.name}' at {device.path}")
    dev_cap = dict(device.capabilities().get(ecodes.EV_ABS, []))  # type: ignore
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
    direction = Direction(analog_x, analog_y, window)
    scroller = Scroller(scroll)

    async for event in device.async_read_loop():  # type: ignore
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
                if not (focus := window.get_focus()):
                    continue
                scroller.update(event, focus)

        elif event.type == ecodes.EV_KEY and event.value == BTN_DOWN:
            # button presses
            if not (focus := window.get_focus()):
                continue
            read_button(event, focus, window)
