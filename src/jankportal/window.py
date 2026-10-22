"""MainWindow class"""

import os
import shlex
import sys
from importlib.metadata import version
from typing import TYPE_CHECKING, cast

if TYPE_CHECKING:
    from collections.abc import Callable
    from typing import Any

import gi

from .assets import _config as CFG
from .joystick.loop import JoystickWrangler
from .lib import find_child_by_name

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("Vte", "3.91")

from gi.repository import (  # noqa: E402
    Adw,
    Gio,
    GLib,
    GObject,
    Gtk,
    Vte,
)

# wait for gobject types or templates break
GObject.type_ensure(Vte.Terminal)

from .ostree.view import OSTreeView  # noqa: E402
from .yafti.view import YaftiView  # noqa: E402


@Gtk.Template(resource_path=f"{CFG.APP_PATH}/ui/settings.ui")
class JankSettings(Adw.PreferencesDialog):
    """Settings Dialog"""

    __gtype_name__ = "JankSettings"
    allow_nvidia: Adw.SwitchRow = Gtk.Template.Child()
    allow_gnome: Adw.SwitchRow = Gtk.Template.Child()


@Gtk.Template(resource_path=f"{CFG.APP_PATH}/ui/app.ui")
class JankWindow(Adw.ApplicationWindow):
    """Main Window"""

    __gtype_name__ = "JankWindow"
    vte: Vte.Terminal = Gtk.Template.Child()
    bottom_sheet: Adw.BottomSheet = Gtk.Template.Child()
    stack: Adw.ViewStack = Gtk.Template.Child()
    command_label: Gtk.Label = Gtk.Template.Child()
    command_status: Gtk.Label = Gtk.Template.Child()
    search: Gtk.SearchEntry = Gtk.Template.Child()
    keep_vte_open: Gtk.ToggleButton = Gtk.Template.Child()
    overlay: Adw.ToastOverlay = Gtk.Template.Child()
    split_view: Adw.OverlaySplitView = Gtk.Template.Child()
    joystick_stack_nav: Gtk.Box = Gtk.Template.Child()
    joystick_main_nav: Gtk.Box = Gtk.Template.Child()
    joystick_vte_nav: Gtk.Box = Gtk.Template.Child()

    def __init__(self, application: Adw.Application, settings: Gio.Settings):
        super().__init__(application=application)
        self.settings = settings
        self._settings_dialog = JankSettings()
        self.settings.bind(
            "allow-nvidia",
            self._settings_dialog.allow_nvidia,
            property="active",
            flags=Gio.SettingsBindFlags.DEFAULT,
        )
        self.settings.bind(
            "allow-gnome",
            self._settings_dialog.allow_gnome,
            property="active",
            flags=Gio.SettingsBindFlags.DEFAULT,
        )
        self.props.title = CFG.APP_TITLE
        self.vte.connect("child-exited", self.on_child_exited)
        self.search.set_key_capture_widget(self)
        self._vte_is_running = False
        self.props.icon_name = "logo"

    def _close_vte(self):
        self.vte.disconnect_by_func(self.on_contents_changed)
        self.vte.reset(clear_history=True, clear_tabstops=True)
        self.bottom_sheet.props.open = False
        if self._joystick_wrangler.has_joystick:
            self.joystick_stack_nav.props.visible = True
            self.joystick_main_nav.props.visible = True

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
            title="About System",
            script=(
                "/usr/bin/fastfetch "
                "--config /usr/share/ublue-os/bazzite/fastfetch.jsonc "
                "--color $(/usr/libexec/bazzite-bling-fastfetch)"
            ),
            vte_done_callback=self.keep_vte_open.activate,
        )
        about = Adw.AboutDialog(
            application_name=CFG.APP_TITLE,
            application_icon="logo",
            developer_name=CFG.AUTHOR,
            comments=CFG.DESCRIPTION,
            version=version(CFG.APP_NAME),
            website=CFG.HOMEPAGE,
            issue_url=CFG.BUG_TRACKER,
            copyright=f"© {CFG.AUTHOR}",
            license_type=getattr(Gtk.License, CFG.GTK_LICENSE),
        )
        about.present(self)

    @Gtk.Template.Callback()
    def on_settings_clicked(self, button: Gtk.Button):
        self._settings_dialog.present(self)

    def on_child_exited(self, terminal: Vte.Terminal, status: int):
        """Countdown from DELAY, then close VTE and unwire the VTE opener"""

        DELAY = 3
        if self._vte_done_callback:
            self._vte_done_callback()
            self._vte_done_callback = None

        self._vte_is_running = False
        title_prefix = "[Exited]" if status == 0 else f"[Exit code {status}]"
        if self.keep_vte_open.props.active:
            self.command_status.props.label = title_prefix
            return

        self.command_status.props.label = f"{title_prefix}, hiding in {DELAY}s…"

        countdown = DELAY

        def delayed_close():
            if self.keep_vte_open.props.active:
                self.command_status.props.label = title_prefix
                return GLib.SOURCE_REMOVE

            nonlocal countdown
            countdown -= 1
            if countdown:
                self.command_status.props.label = (
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
            self.info("Action Failed", error.message)
            return

        self._vte_is_running = True
        self.command_status.props.label = "[Running]"
        self.vte.connect("contents-changed", self.on_contents_changed)

    def on_contents_changed(self, terminal: Vte.Terminal):
        """Show VTE if script has output anything"""

        self.bottom_sheet.props.open = True
        self.vte.grab_focus()
        if self._joystick_wrangler.has_joystick:
            self.joystick_stack_nav.props.visible = False
            self.joystick_main_nav.props.visible = False

    def command_runner(
        self,
        title: str,
        script: str,
        vte_done_callback: Callable[[], Any] | None = None,
    ) -> None:
        """Pass script to terminal widget"""

        self._vte_done_callback = vte_done_callback
        self.command_label.props.label = title

        # intercept use of "yad" in scripts, convert to window.info dialog
        if "yad" in script:
            lines: list[str] = []
            dlg_title = ""
            text = ""
            button = ""
            for command in script.split("&&"):
                if "yad" not in command:
                    lines.append(command.strip())
                    continue
                tokens = shlex.split(command)
                for idx, token in enumerate(tokens):
                    if "title" in token:
                        dlg_title = token.split("=")[1]
                        continue
                    if "text" in token:
                        text = tokens[idx + 1]
                        continue
                    if "button" in token:
                        button = token.split("=")[1].split("!")[0]
                        continue
            new_script = " && ".join(lines)
            self.info(
                title=dlg_title,
                message=text,
                button=button,
                callback=lambda _d, _r: self.command_runner(
                    title, new_script, vte_done_callback
                ),
            )
            return

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

    def info(
        self,
        title: str,
        message: str,
        button: str = "OK",
        callback: Callable[[Gtk.Widget, str], None] | None = None,
    ) -> None:
        """Display non critical error"""

        dialog = Adw.AlertDialog.new(title, message)
        dialog.add_response("ok", button)
        dialog.set_default_response("ok")
        dialog.set_close_response("ok")
        dialog.choose(self, cancellable=None, callback=callback)

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
        parent = cast("Gtk.Widget", self.stack.get_child_by_name("welcome"))
        starter_focus = cast(
            "Gtk.Widget", find_child_by_name(parent, "bazzite-documentation")
        )
        starter_focus.grab_focus()
        self.ostree_view = OSTreeView(self)
        placeholder = Adw.Bin(
            child=Adw.StatusPage(
                title="Wait a moment",
                description="Loading Deployments UI.",
            )
        )
        self.stack.add_titled(child=placeholder, name="ostree", title="Deployments")
        self._joystick_wrangler = JoystickWrangler(self)
        self._joystick_wrangler.bind_property(
            source_property="has_joystick",
            target=self.joystick_main_nav,
            target_property="visible",
            flags=GObject.BindingFlags.SYNC_CREATE,
        )
        self._joystick_wrangler.bind_property(
            source_property="has_joystick",
            target=self.joystick_stack_nav,
            target_property="visible",
            flags=GObject.BindingFlags.SYNC_CREATE,
        )
        self._joystick_wrangler.bind_property(
            source_property="has_joystick",
            target=self.joystick_vte_nav,
            target_property="visible",
            flags=GObject.BindingFlags.SYNC_CREATE,
        )
        await self.ostree_view.initialize()
