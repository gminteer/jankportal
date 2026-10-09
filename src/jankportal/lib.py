"""Helper functions used in at least two different files"""

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk  # noqa: E402


# Can't mess with encapsulated child widgets from a blueprint
def align_drop_down(drop_down: Gtk.DropDown, halign: Gtk.Align = Gtk.Align.END) -> None:
    """Change a drop down's pop over's horizontal alignment"""
    child = drop_down.get_first_child()
    while child is not None:
        if isinstance(child, Gtk.Popover):
            child.props.halign = halign
            break

        child = child.get_next_sibling()


def find_child_by_name(parent: Gtk.Widget, name: str) -> Gtk.Widget | None:
    """Loop through children until we hit one with a matching name"""
    if parent.props.name == name:
        return parent
    child = parent.get_first_child()
    while child is not None:
        if result := find_child_by_name(child, name):
            return result
        child = child.get_next_sibling()
    return None
