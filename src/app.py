import os
import subprocess
import sys
from typing import Any

import gi

from ostree import OSTreeUI
from yafti import YaftiUI

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("Vte", "3.91")

from gi.repository import Adw, Gdk, Gio, GLib, GObject, Gtk, Vte  # noqa: E402

# Wait until Vte resolves as a GObject that exists
GObject.type_ensure(Vte.Terminal.__gtype__)  # type: ignore


def compile_blp(blp: str):
    """Compile GTK Blueprint

    (runs blueprint-compiler in a subprocess)

    :param blp: Blueprint filename
    :type blp: str
    :return: XML UI template
    :rtype: str
    """
    try:
        result = subprocess.run(
            ["blueprint-compiler", "compile", blp],
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout

    except FileNotFoundError:
        print("blueprint-compiler not in $PATH", file=sys.stderr)
        sys.exit(1)

    except subprocess.CalledProcessError as error:
        print(f"Blueprint error: {error.stderr}", file=sys.stderr)
        sys.exit(1)


@Gtk.Template(string=compile_blp("src/ui/app.blp"))
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

    def __init__(self, **kwargs: Any):
        super().__init__(**kwargs)
        self.vte.connect("child-exited", self.on_child_exited)
        self.search_entry.set_key_capture_widget(self)
        self._vte_is_running = False

    @Gtk.Template.Callback()
    def on_keep_vte_open_clicked(self, button: Gtk.ToggleButton):
        if self.keep_vte_open.props.active:
            self.keep_vte_open.props.icon_name = "window-unpin-symbolic"
            return
        self.keep_vte_open.props.icon_name = "window-pin-symbolic"
        if not self._vte_is_running and self.bottom_sheet.props.open:
            self.bottom_sheet.props.open = False

    def on_child_exited(self, terminal: Vte.Terminal, status: int):
        """Delay, then hide terminal window after script exit"""

        self._vte_is_running = False
        if self.keep_vte_open.props.active:
            self.command_label.props.label = "[Exited], unpin to close window"
            return

        DELAY = 3
        self.command_label.props.label = f"[Exited], hiding in {DELAY}s…"
        countdown = DELAY

        # Hide bottom sheet, unwire bottom sheet opener
        def delayed_close():
            nonlocal countdown
            countdown -= 1
            if countdown:
                self.command_label.props.label = f"[Exited], hiding in {countdown}s…"
                return GLib.SOURCE_CONTINUE
            self.bottom_sheet.props.open = False
            self.vte.disconnect_by_func(self.on_contents_changed)
            return GLib.SOURCE_REMOVE

        GLib.timeout_add_seconds(1, delayed_close)
        if status != 0:
            print(f"Command returned non-zero status: {status}", file=sys.stderr)

    def on_spawn_complete(
        self, terminal: Vte.Terminal | None, pid: int, error: GLib.Error | None
    ):
        """Wire up VTE contents-changed signal after script is spawned"""

        if error:
            print(f"error: {error.message}", file=sys.stderr)
            return

        self._vte_is_running = True
        self.vte.connect("contents-changed", self.on_contents_changed)

    def on_contents_changed(self, terminal: Vte.Terminal | None):
        """Show terminal widget if script has output anything"""

        self.bottom_sheet.props.open = True
        self.vte.grab_focus()

    def command_runner(self, title: str, script: str):
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

    def append_components(self):
        """Add ViewStackPages to main window"""

        self.yafti_ui = YaftiUI(self)
        self.ostree_ui = OSTreeUI(self)
        self.stack.props.visible_child_name = "welcome"


class JankPortalApp(Adw.Application):
    """App class for Jank Portal"""

    def __init__(self, **kwargs: Any):
        super().__init__(
            application_id="com.github.gminteer.jankportal",
            flags=Gio.ApplicationFlags.DEFAULT_FLAGS,
            **kwargs,
        )

    def do_activate(self):
        """Load CSS and main window, show main window"""

        css = Gtk.CssProvider()
        css.load_from_path("src/ui/app.css")
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


if __name__ == "__main__":
    main()
