from enum import Enum

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk  # noqa: E402


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


# Can't mess with encapsulated child widgets from a blueprint
def align_drop_down(drop_down: Gtk.DropDown, halign: Gtk.Align = Gtk.Align.END) -> None:
    """Change a drop down's pop over's horizontal alignment"""
    child = drop_down.get_first_child()
    while child is not None:
        if isinstance(child, Gtk.Popover):
            child.props.halign = halign
            break

        child = child.get_next_sibling()
