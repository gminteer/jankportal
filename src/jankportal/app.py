import asyncio
import os
import sys
from importlib.metadata import version
from importlib.resources import files
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable

import gi
from gi.events import GLibEventLoopPolicy

from . import _config as CFG
from .lib import APP_ID, APP_PATH

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("Vte", "3.91")

from gi.repository import Adw, Gdk, Gio, GLib, GObject, Gtk, Vte  # noqa: E402

# Wait until VTE resolves
GObject.type_ensure(Vte.Terminal.__gtype__)  # type: ignore

# Load GTK resources
resource_blob = files("jankportal").joinpath("jankportal.gresource").read_bytes()
resource = Gio.Resource.new_from_data(GLib.Bytes.new(resource_blob))
Gio.resources_register(resource)

# Need resources loaded first
from .ostree.view import OSTreeView  # noqa: E402
from .yafti.view import YaftiView  # noqa: E402


def find_child_by_name(parent: Gtk.Widget, name: str) -> Gtk.Widget | None:
    """Loop through children until we hit one with a matching name"""
    if parent.props.name == name:
        return parent
    child = parent.get_first_child()
    while child is not None:
        result = find_child_by_name(child, name)
        if result is not None:
            return result
        child = child.get_next_sibling()
    return None


@Gtk.Template(resource_path=f"{APP_PATH}/ui/app.ui")
class JankPortalWindow(Adw.ApplicationWindow):
    """Main window for Jank Portal"""

    __gtype_name__ = "JankPortalWindow"
    vte: Vte.Terminal = Gtk.Template.Child()
    bottom_sheet: Adw.BottomSheet = Gtk.Template.Child()
    stack: Adw.ViewStack = Gtk.Template.Child()
    command_label: Gtk.Label = Gtk.Template.Child()
    search: Gtk.SearchEntry = Gtk.Template.Child()
    keep_vte_open: Gtk.ToggleButton = Gtk.Template.Child()
    overlay: Adw.ToastOverlay = Gtk.Template.Child()
    split_view: Adw.OverlaySplitView = Gtk.Template.Child()

    def __init__(self, application: Adw.Application):
        super().__init__(application=application)
        self.vte.connect("child-exited", self.on_child_exited)
        self.search.set_key_capture_widget(self)
        self._vte_is_running = False

    def _close_vte(self):
        self.vte.disconnect_by_func(self.on_contents_changed)
        self.vte.reset(clear_history=True, clear_tabstops=True)
        self.bottom_sheet.props.open = False

    @Gtk.Template.Callback()
    def on_keep_vte_open_clicked(self, button: Gtk.ToggleButton):
        """Change button icon, close VTE sheet if unpinned and VTE not active"""

        if self.keep_vte_open.props.active:
            self.keep_vte_open.props.icon_name = "window-unpin-symbolic"
            return
        self.keep_vte_open.props.icon_name = "window-pin-symbolic"

        if not self._vte_is_running and self.bottom_sheet.props.open:
            self._close_vte()

    @Gtk.Template.Callback()
    def on_about_clicked(self, button: Gtk.Button):
        about = Adw.AboutDialog(
            application_name="Jank Portal",
            developer_name=CFG.AUTHOR,
            comments=CFG.DESCRIPTION,
            version=version("jankportal"),
            website=CFG.HOMEPAGE,
            issue_url=CFG.BUG_TRACKER,
            copyright=f"© 2026 {CFG.AUTHOR}",
            license_type=Gtk.License.GPL_3_0,
        )
        about.present(self)

    def on_child_exited(self, terminal: Vte.Terminal, status: int):
        """Countdown from DELAY, then close VTE sheet and unwire bottom sheet opener"""

        if self._vte_done_callback is not None:
            self._vte_done_callback()  # type: ignore

        self._vte_is_running = False
        title_prefix = "[Exited]" if status == 0 else f"[Exited with code {status}]"
        if self.keep_vte_open.props.active:
            self.command_label.props.label = f"{title_prefix}, unpin to close"
            return

        DELAY = 3
        self.command_label.props.label = f"{title_prefix}, hiding in {DELAY}s…"
        countdown = DELAY

        def delayed_close():
            if self.keep_vte_open.props.active:
                self.command_label.props.label = f"{title_prefix}, unpin to close"
                return GLib.SOURCE_REMOVE

            nonlocal countdown
            countdown -= 1
            if countdown:
                self.command_label.props.label = (
                    f"{title_prefix}, hiding in {countdown}s…"
                )
                return GLib.SOURCE_CONTINUE

            self._close_vte()
            return GLib.SOURCE_REMOVE

        GLib.timeout_add_seconds(1, delayed_close)

    def on_spawn_complete(
        self, terminal: Vte.Terminal, pid: int, error: GLib.Error | None
    ):
        """Wire up VTE contents-changed signal after script is spawned"""

        if error:
            self.warn("Action Failed", error.message)
            return

        self._vte_is_running = True
        self.vte.connect("contents-changed", self.on_contents_changed)

    def on_contents_changed(self, terminal: Vte.Terminal):
        """Show terminal widget if script has output anything"""

        self.bottom_sheet.props.open = True
        self.vte.grab_focus()

    def command_runner(
        self,
        title: str,
        script: str,
        vte_done_callback: Callable[[], None] | None = None,
    ) -> None:
        """Pass script to terminal widget"""
        self._vte_done_callback = vte_done_callback
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

    def warn(self, title: str, message: str) -> None:
        """Display non critical error"""

        dialog = Adw.AlertDialog.new(title, message)
        dialog.add_response("ok", "OK")
        dialog.set_default_response("ok")
        dialog.set_close_response("ok")
        dialog.choose(self, cancellable=None)

    def panic(self, message: str) -> None:
        """Display critical failure and exit program"""

        def on_response(dialog: Adw.AlertDialog, response: str):
            sys.exit(1)

        dialog = Adw.AlertDialog.new("Fatal Error", message)
        dialog.add_response("ok", "Close Program")
        dialog.set_default_response("ok")
        dialog.set_close_response("ok")
        dialog.choose(self, cancellable=None, callback=on_response)

    def toast(self, message: str) -> None:
        """Display message in toast"""

        self.overlay.add_toast(Adw.Toast.new(message))

    async def initialize(self) -> None:
        """Add ViewStackPages to main window and connect joystick input"""

        self.yafti_view = YaftiView(self)
        self.stack.props.visible_child_name = "welcome"
        parent = self.stack.get_child_by_name("welcome")
        if parent is not None:
            starter_focus = find_child_by_name(parent, "bazzite-documentation")
            if starter_focus is not None:
                starter_focus.grab_focus()
        self.ostree_view = OSTreeView(self)
        placeholder = Adw.Bin(
            child=Adw.StatusPage(
                title="Wait a moment",
                description="Loading Deployments UI.",
            )
        )
        self.stack.add_titled(child=placeholder, name="ostree", title="Deployments")
        await self.ostree_view.initialize()


class JankPortalApp(Adw.Application):
    """App class for Jank Portal"""

    def __init__(self):
        super().__init__(application_id=APP_ID)

    def _async_cleanup(self, task: asyncio.Task[None]):
        """Drop reference to async init task"""
        del self._async_init

    def do_activate(self):
        """Load CSS and main window, show main window"""

        css = Gtk.CssProvider()
        css.load_from_resource(f"{APP_PATH}/css/app.css")
        display = Gdk.Display.get_default()
        if display:
            Gtk.StyleContext.add_provider_for_display(
                display=display,
                provider=css,
                priority=Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
            )
        win = JankPortalWindow(application=self)
        self._async_init = asyncio.create_task(win.initialize())
        self._async_init.add_done_callback(self._async_cleanup)
        win.present()


def main():
    app = JankPortalApp()
    policy = GLibEventLoopPolicy()
    asyncio.set_event_loop_policy(policy)  # type: ignore
    return app.run(sys.argv)
