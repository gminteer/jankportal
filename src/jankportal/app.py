import asyncio
import os
import sys
import tempfile
from importlib.metadata import version
from importlib.resources import files
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable

import gi
from gi.events import GLibEventLoopPolicy

from . import _config as CFG
from .joystick.loop import read_joystick

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("Vte", "3.91")

from gi.repository import (  # noqa: E402
    Adw,
    Gdk,
    Gio,
    GLib,
    GObject,
    Gtk,
    PangoCairo,
    Vte,
)

# Wait until VTE resolves
GObject.type_ensure(Vte.Terminal.__gtype__)  # type: ignore

# Load GTK resources
resource_blob = files(CFG.APP_NAME).joinpath(f"{CFG.APP_NAME}.gresource").read_bytes()
resource = Gio.Resource.new_from_data(GLib.Bytes.new(resource_blob))
Gio.resources_register(resource)

# Load in button symbol font
font_blob = Gio.resources_lookup_data(
    f"{CFG.APP_PATH}/font/promptfont.ttf", Gio.ResourceLookupFlags.NONE
).get_data()
if font_blob:  # I wonder if i should invert this and blow up if it fails?
    with tempfile.NamedTemporaryFile(suffix=".ttf") as temp:
        temp.write(font_blob)  # you apparently can't just give Pango a bytestream
        font_map = PangoCairo.font_map_get_default()
        font_map.add_font_file(temp.name)

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


@Gtk.Template(resource_path=f"{CFG.APP_PATH}/ui/app.ui")
class JankWindow(Adw.ApplicationWindow):
    """Main Window"""

    __gtype_name__ = "JankWindow"
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
        self.props.title = CFG.APP_TITLE
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
        self.command_runner(
            "About System",
            "/usr/bin/bash --noprofile --norc -lc\
            /usr/bin/fastfetch\
                -c /usr/share/ublue-os/bazzite/fastfetch.jsonc\
                --color $(/usr/libexec/bazzite-bling-fastfetch)",
        )
        self.keep_vte_open.activate()
        about = Adw.AboutDialog(
            application_name=CFG.APP_TITLE,
            developer_name=CFG.AUTHOR,
            comments=CFG.DESCRIPTION,
            version=version(CFG.APP_NAME),
            website=CFG.HOMEPAGE,
            issue_url=CFG.BUG_TRACKER,
            copyright=f"© {CFG.AUTHOR}",
            license_type=getattr(Gtk.License, CFG.GTK_LICENSE),
        )
        about.present(self)

    def on_child_exited(self, terminal: Vte.Terminal, status: int):
        """Countdown from DELAY, then close VTE and unwire the VTE opener"""

        DELAY = 3
        if self._vte_done_callback is not None:
            self._vte_done_callback()  # type: ignore
            self._vte_done_callback = None

        self._vte_is_running = False
        title_prefix = "[Exited]" if status == 0 else f"[Exited with code {status}]"
        if self.keep_vte_open.props.active:
            self.command_label.props.label = f"{title_prefix}, unpin to close"
            return

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
        """Show VTE if script has output anything"""

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
        self._read_joystick = asyncio.create_task(read_joystick(self))
        await self.ostree_view.initialize()


class JankApplication(Adw.Application):
    """Application"""

    def __init__(self):
        super().__init__(application_id=CFG.APP_ID)

    def _async_cleanup(self, task: asyncio.Task[None]):
        """Drop reference to async init task"""
        del self._async_init

    def do_activate(self):
        """Load CSS and main window, show main window"""

        css = Gtk.CssProvider()
        css.load_from_resource(f"{CFG.APP_PATH}/css/app.css")
        display = Gdk.Display.get_default()
        if display:
            Gtk.StyleContext.add_provider_for_display(
                display=display,
                provider=css,
                priority=Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
            )
        win = JankWindow(application=self)
        self._async_init = asyncio.create_task(win.initialize())
        self._async_init.add_done_callback(self._async_cleanup)
        win.present()


def main():
    app = JankApplication()
    policy = GLibEventLoopPolicy()
    asyncio.set_event_loop_policy(policy)  # type: ignore
    return app.run(sys.argv)
