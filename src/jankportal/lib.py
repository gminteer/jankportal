import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk  # noqa: E402

APP_PATH = "/io/github/gminteer/jankportal"


class JankWarning(UserWarning):
    """Raised on non-fatal errors"""

    def __init__(self, title: str, message: str):
        super().__init__(self)
        self.title = title
        self.message = message


# Can't mess with encapsulated child widgets from a blueprint
def align_drop_down(drop_down: Gtk.DropDown, halign: Gtk.Align = Gtk.Align.END) -> None:
    """Change a drop down's pop over's horizontal alignment"""
    child = drop_down.get_first_child()
    while child is not None:
        if isinstance(child, Gtk.Popover):
            child.props.halign = halign
            break

        child = child.get_next_sibling()
