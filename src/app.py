import gi
import os
import subprocess
import sys

from typing import Any, Optional

from ostree import OSTreeUI
from yafti import YaftiUI

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("Vte", "3.91")

from gi.repository import Gdk, Gio, GLib, GObject, Gtk, Adw, Vte

# Wait until Vte resolves as GObjects that exist
GObject.type_ensure(Vte.Terminal.__gtype__)  # type: ignore


def compile_blp(blp: str):
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
    __gtype_name__ = "JankPortalWindow"
    vte = Gtk.Template.Child()
    bottom_sheet = Gtk.Template.Child()
    stack = Gtk.Template.Child()

    def __init__(self, **kwargs: Any):
        super().__init__(**kwargs)
        self.vte.connect("child-exited", self.on_child_exited)

    def on_child_exited(self, terminal: Vte.Terminal, status: int):
        self.bottom_sheet.props.open = False

    def on_spawn_complete(
        self, terminal: Optional[Vte.Terminal], pid: int, error: Optional[GLib.Error]
    ):
        pass

    def command_runner(self, script: str):
        self.bottom_sheet.props.open = True
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
        self.yafti_ui = YaftiUI(self)
        self.ostree_ui = OSTreeUI(self)


class JankPortalApp(Adw.Application):
    def __init__(self):
        super().__init__(
            application_id="com.github.gminteer.jankportal",
            flags=Gio.ApplicationFlags.DEFAULT_FLAGS,
        )

    def do_activate(self):
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
