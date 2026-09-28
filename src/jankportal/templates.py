import gi

from .lib import APP_PATH

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("WebKit", "6.0")

from gi.repository import Adw, GObject, Gtk, WebKit  # noqa: E402

# Wait for WebKit to resolve
GObject.type_ensure(WebKit.WebView.__gtype__)  # type: ignore


class OSTree:
    """Namespace for OSTree Templates"""

    @Gtk.Template(resource_path=f"{APP_PATH}/ostree/changelog.ui")
    class Changelog(Adw.Dialog):
        __gtype_name__ = "Changelog"
        bar: Adw.WindowTitle = Gtk.Template.Child()
        web_view: WebKit.WebView = Gtk.Template.Child()

    @Gtk.Template(resource_path=f"{APP_PATH}/ostree/deployment_actions.ui")
    class DeploymentActions(Gtk.ListBox):
        __gtype_name__ = "OSTreeDeploymentActions"
        pin: Adw.SwitchRow = Gtk.Template.Child()
        rebase: Adw.ActionRow = Gtk.Template.Child()

    @Gtk.Template(resource_path=f"{APP_PATH}/ostree/overlay_list.ui")
    class OverlayList(Gtk.Box):
        __gtype_name__ = "OSTreeOverlayList"
        list: Gtk.ListBox = Gtk.Template.Child()

    @Gtk.Template(resource_path=f"{APP_PATH}/ostree/page.ui")
    class Page(Gtk.ScrolledWindow):
        __gtype_name__ = "OSTreePage"
        container: Gtk.Box = Gtk.Template.Child()
        image: Gtk.DropDown = Gtk.Template.Child()
        tag: Gtk.DropDown = Gtk.Template.Child()
        img_reset: Adw.ButtonRow = Gtk.Template.Child()
        img_rebase: Adw.ButtonRow = Gtk.Template.Child()

    @Gtk.Template(resource_path=f"{APP_PATH}/ostree/row.ui")
    class Row(Adw.ExpanderRow):
        __gtype_name__ = "OSTreeRow"
        icon_box: Gtk.Box = Gtk.Template.Child()
        changelog: Gtk.Button = Gtk.Template.Child()


class Yafti:
    """Namespace for YAFTI Templates"""

    @Gtk.Template(resource_path=f"{APP_PATH}/yafti/page.ui")
    class Page(Gtk.ScrolledWindow):
        __gtype_name__ = "YaftiPage"
        description: Gtk.Label = Gtk.Template.Child()
        action_list: Gtk.ListBox = Gtk.Template.Child()
