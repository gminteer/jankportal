"""handle joystick button presses"""

from typing import TYPE_CHECKING

import gi
from evdev import categorize, ecodes

if TYPE_CHECKING:
    from evdev import InputEvent

    from jankportal.window import JankWindow

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gtk  # noqa: E402


def read_button(event: InputEvent, focus: Gtk.Widget, window: JankWindow):
    match event.code:
        case ecodes.BTN_SOUTH:
            # south button = enter
            if focus.activate():
                return

            expander = focus.get_ancestor(Adw.ExpanderRow)
            if expander:
                expander.props.expanded = True
            return

        case ecodes.BTN_EAST:
            # east button = escape

            if isinstance(focus, Gtk.Text):
                if search := focus.get_ancestor(Gtk.SearchEntry):
                    search.emit("stop-search")
                return

            if dialog := focus.get_ancestor(Adw.Dialog):
                dialog.close()
                return

            if expander := focus.get_ancestor(Adw.ExpanderRow):
                expander.props.expanded = False
                return

            if dropdown := focus.get_ancestor(Gtk.DropDown):
                child = dropdown.get_first_child()
                while child is not None:
                    if isinstance(child, Gtk.Popover):
                        child.popdown()
                        break
                    child = child.get_next_sibling()
                return

        case ecodes.BTN_NORTH:
            # north button = focus search entry
            window.search.grab_focus()

        case ecodes.BTN_TL:
            # left trigger = previous viewstack page
            if not (current_page := window.stack.get_visible_child()):
                return
            page = window.stack.get_first_child()
            idx = 0
            wait_for_last_page = False
            while page is not None:
                if page.get_next_sibling() == current_page:
                    if idx == 0:
                        # search results are the first page in the stack
                        # so if the search page's next sibling is a match,
                        # loop to the end instead
                        wait_for_last_page = True
                    else:
                        window.stack.set_visible_child(page)
                        return
                if page.get_next_sibling() is None and wait_for_last_page:
                    window.stack.set_visible_child(page)
                    return
                idx += 1
                page = page.get_next_sibling()

        case ecodes.BTN_TR:
            # right tigger = next viewstack page
            if not (page := window.stack.get_visible_child()):
                return
            if not (next_page := page.get_next_sibling()):
                next_page = window.stack.get_first_child()
                if not next_page:
                    return
                # search results are the first page in the stack
                next_page = next_page.get_next_sibling()
                if not next_page:
                    return
            window.stack.set_visible_child(next_page)

        case ecodes.BTN_START:
            # start button = show about dialog
            window.on_about_clicked(None)

        case _:
            data = categorize(event)
            print(f"Code: {event.code}, Value: {event.value}, Category: {data}")
