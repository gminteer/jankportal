"""UI templates for YAFTI pages"""

import gi

from jankportal._config import APP_PATH

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gtk  # noqa:E402


@Gtk.Template(resource_path=f"{APP_PATH}/ui/yafti/page.ui")
class Page(Gtk.ScrolledWindow):
    __gtype_name__ = "YaftiPage"
    description: Gtk.Label = Gtk.Template.Child()
    action_list: Gtk.ListBox = Gtk.Template.Child()


@Gtk.Template(resource_path=f"{APP_PATH}/ui/yafti/expander_row.ui")
class ExpanderRow(Adw.ExpanderRow):
    __gtype_name__ = "YaftiExpanderRow"
    emblem_box: Gtk.Box = Gtk.Template.Child()
    container: Gtk.ListBox = Gtk.Template.Child()


@Gtk.Template(resource_path=f"{APP_PATH}/ui/yafti/drop_down_row.ui")
class DropDownRow(Adw.ActionRow):
    __gtype_name__ = "YaftiDropDownRow"
    emblem_box: Gtk.Box = Gtk.Template.Child()
    drop_down: Gtk.DropDown = Gtk.Template.Child()


@Gtk.Template(resource_path=f"{APP_PATH}/ui/yafti/button_group_row.ui")
class ButtonGroupRow(Adw.ActionRow):
    __gtype_name__ = "YaftiButtonGroupRow"
    emblem_box: Gtk.Box = Gtk.Template.Child()
    action_box: Gtk.Box = Gtk.Template.Child()
