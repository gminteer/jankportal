import os
import sys
from pathlib import Path

import gi

from .lib import RES_PATH

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("Vte", "3.91")

from gi.repository import Adw, Gdk, Gio, GLib, GObject, Gtk, Vte  # noqa: E402

# Wait until VTE resolves
GObject.type_ensure(Vte.Terminal.__gtype__)  # type: ignore

# Load GTK resources
resource_path = Path(__file__).parent / "resources.gresource"
resource = Gio.Resource.load(str(resource_path))
Gio.resources_register(resource)

# Need resources loaded first
from .ostree import OSTreeUI  # noqa: E402
from .yafti import YaftiUI  # noqa: E402


@Gtk.Template(resource_path=f"{RES_PATH}/app.ui")
class JankPortalWindow(Adw.ApplicationWindow):
    """Main window for Jank Portal"""

    __gtype_name__ = "JankPortalWindow"
    vte: Vte.Terminal = Gtk.Template.Child()
    bottom_sheet: Adw.BottomSheet = Gtk.Template.Child()
    stack: Adw.ViewStack = Gtk.Template.Child()
    command_label: Gtk.Label = Gtk.Template.Child()
    search_bar: Gtk.SearchBar = Gtk.Template.Child()
    search_entry: Gtk.SearchEntry = Gtk.Template.Child()
    keep_vte_open: Gtk.ToggleButton = Gtk.Template.Child()
    overlay: Adw.ToastOverlay = Gtk.Template.Child()

    def __init__(self, application: Adw.Application):
        super().__init__(application=application)
        self.vte.connect("child-exited", self.on_child_exited)
        self.search_entry.set_key_capture_widget(self)
        self._vte_is_running = False

    @Gtk.Template.Callback()
    def on_keep_vte_open_clicked(self, button: Gtk.ToggleButton):
        """Change button icon, close VTE sheet if unpinned and VTE not active"""

        if self.keep_vte_open.props.active:
            self.keep_vte_open.props.icon_name = "window-unpin-symbolic"
            return
        self.keep_vte_open.props.icon_name = "window-pin-symbolic"

        if not self._vte_is_running and self.bottom_sheet.props.open:
            self.vte.disconnect_by_func(self.on_contents_changed)
            self.bottom_sheet.props.open = False

    @Gtk.Template.Callback()
    def on_about_clicked(self, button: Gtk.Button):
        about = Adw.AboutDialog(
            application_name="Jank Portal",
            developer_name="h3lmut",
            comments="yafti-gtk, re-imagined by a madman",
            website="https://github.com/gminteer/jankportal#README",
            issue_url="https://github.com/gminteer/jankportal/issues",
            copyright="©️ 2026 h3lmut",
            license_type=Gtk.License.GPL_3_0,
        )
        about.present(self)

    def on_child_exited(self, terminal: Vte.Terminal, status: int):
        """Countdown from DELAY, then close VTE sheet and unwire bottom sheet opener"""

        self._vte_is_running = False
        if self.keep_vte_open.props.active:
            self.command_label.props.label = "[Exited], unpin to close window"
            return

        DELAY = 3
        self.command_label.props.label = f"[Exited], hiding in {DELAY}s…"
        countdown = DELAY

        def delayed_close():
            nonlocal countdown
            countdown -= 1
            if countdown:
                self.command_label.props.label = f"[Exited], hiding in {countdown}s…"
                return GLib.SOURCE_CONTINUE

            self.bottom_sheet.props.open = False
            # Not sure if bad things happen if you connect a handler up to a signal
            # multiple times, so unplug it here
            self.vte.disconnect_by_func(self.on_contents_changed)
            return GLib.SOURCE_REMOVE

        GLib.timeout_add_seconds(1, delayed_close)
        if status != 0:
            self.show_error(f"Command returned non-zero status: {status}")

    def on_spawn_complete(
        self, terminal: Vte.Terminal, pid: int, error: GLib.Error | None
    ):
        """Wire up VTE contents-changed signal after script is spawned"""

        if error:
            self.show_error(f"error: {error.message}")
            return

        self._vte_is_running = True
        self.vte.connect("contents-changed", self.on_contents_changed)

    def on_contents_changed(self, terminal: Vte.Terminal):
        """Show terminal widget if script has output anything"""

        self.bottom_sheet.props.open = True
        self.vte.grab_focus()

    def command_runner(self, title: str, script: str) -> None:
        """Pass script to terminal widget"""

        self.command_label.props.label = title
        self.vte.spawn_async(
            pty_flags=Vte.PtyFlags.DEFAULT,
            working_directory=os.environ.get("HOME"),
            argv=["/bin/bash", "--noprofile", "--norc", "-lc", script],
            envv=None,
            spawn_flags=GLib.SpawnFlags.DEFAULT,
            child_setup=None,
            timeout=-1,
            callback=self.on_spawn_complete,
        )

    def show_error(self, message: str) -> None:
        toast = Adw.Toast.new(message)
        self.overlay.add_toast(toast)

    def append_components(self) -> None:
        """Add ViewStackPages to main window"""

        self.yafti_ui = YaftiUI(self)
        self.ostree_ui = OSTreeUI(self)
        self.stack.props.visible_child_name = "welcome"


class JankPortalApp(Adw.Application):
    """App class for Jank Portal"""

    def __init__(self):
        super().__init__(
            application_id="io.github.gminteer.jankportal",
            flags=Gio.ApplicationFlags.DEFAULT_FLAGS,
        )

    def do_activate(self):
        """Load CSS and main window, show main window"""

        css = Gtk.CssProvider()
        css.load_from_resource(f"{RES_PATH}/app.css")
        display = Gdk.Display.get_default()
        if display:
            Gtk.StyleContext.add_provider_for_display(
                display=display,
                provider=css,
                priority=Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
            )
        win = JankPortalWindow(application=self)
        win.append_components()
        win.present()


def main():
    app = JankPortalApp()
    return app.run(sys.argv)
