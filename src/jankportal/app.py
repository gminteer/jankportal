"""High-level GTK / Python application housekeeping stuff"""

import asyncio
import sys
from importlib import resources

import gi
from gi.events import GLibEventLoopPolicy

from .assets import _config as CFG

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("Vte", "3.91")

from gi.repository import (  # noqa: E402
    Adw,
    Gdk,
    Gio,
    GLib,
    Gtk,
    PangoCairo,
)

if not (display := Gdk.Display.get_default()):
    print("No default GDK display?!", file=sys.stderr)
    sys.exit(1)

# load resources
resource = Gio.Resource.new_from_data(
    GLib.Bytes.new(
        resources.files(CFG.APP_NAME)
        .joinpath(f"assets/{CFG.APP_NAME}.gresource")
        .read_bytes()
    )
)
Gio.resources_register(resource)

# load fonts and settings schema
font_map = PangoCairo.FontMap.get_default()
with resources.as_file(resources.files(CFG.APP_NAME).joinpath("assets")) as asset_path:
    schema = Gio.SettingsSchemaSource.new_from_directory(
        directory=str(asset_path),
        parent=Gio.SettingsSchemaSource.get_default(),
        trusted=False,
    ).lookup(CFG.APP_ID, recursive=False)

    for font in asset_path.rglob("*.[ot]tf"):
        font_map.add_font_file(str(font))

# tell IconTheme we got an icon
icon_theme = Gtk.IconTheme.get_for_display(display)
icon_theme.add_resource_path(CFG.APP_PATH)

# load CSS
css = Gtk.CssProvider()
css.load_from_resource(f"{CFG.APP_PATH}/css/app.css")
Gtk.StyleContext.add_provider_for_display(
    display=display,
    provider=css,
    priority=Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
)

# have to load in GTK resources before importing the window
from .window import JankWindow  # noqa: E402


class JankApplication(Adw.Application):
    __gtype_name__ = "JankApplication"

    def __init__(self):
        super().__init__(application_id=CFG.APP_ID)
        if not schema:
            raise RuntimeError(f"Missing schema: '{CFG.APP_ID}'")
        self.settings = Gio.Settings.new_full(schema)

    def _async_cleanup(self, task: asyncio.Task[None]):
        """Drop reference to async init task"""
        del self._async_init

    def do_activate(self):
        """Show main window, kick off async init"""

        win = JankWindow(application=self, settings=self.settings)

        self._async_init = asyncio.create_task(win.initialize())
        self._async_init.add_done_callback(self._async_cleanup)

        win.present()


def main():
    # this is deprecated, but it'll work until Python 3.16
    asyncio.set_event_loop_policy(GLibEventLoopPolicy())  # type: ignore

    app = JankApplication()
    return app.run(sys.argv)
