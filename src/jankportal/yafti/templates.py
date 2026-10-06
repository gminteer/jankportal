import gi

from jankportal._config import APP_PATH

gi.require_version("Gtk", "4.0")

from gi.repository import Gtk  # noqa:E402


@Gtk.Template(resource_path=f"{APP_PATH}/ui/yafti/page.ui")
class Page(Gtk.ScrolledWindow):
    __gtype_name__ = "YaftiPage"
    description: Gtk.Label = Gtk.Template.Child()
    action_list: Gtk.ListBox = Gtk.Template.Child()
