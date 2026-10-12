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

# load resources
resource_blob = (
    resources.files(CFG.APP_NAME)
    .joinpath(f"assets/{CFG.APP_NAME}.gresource")
    .read_bytes()
)
resource = Gio.Resource.new_from_data(GLib.Bytes.new(resource_blob))
Gio.resources_register(resource)

# load fonts and settings schema
font_map = PangoCairo.FontMap.get_default()
with resources.as_file(resources.files(CFG.APP_NAME).joinpath("assets")) as asset_path:
    schema_source = Gio.SettingsSchemaSource.new_from_directory(
        str(asset_path),
        parent=Gio.SettingsSchemaSource.get_default(),
        trusted=False,
    )
    schema = schema_source.lookup(CFG.APP_ID, recursive=False)
    for font in asset_path.rglob("*.[ot]tf"):
        font_map.add_font_file(str(font))

# have to load in GTK resources before importing the window
from .window import JankWindow  # noqa: E402


class JankApplication(Adw.Application):
    def __init__(self):
        super().__init__(application_id=CFG.APP_ID)
        if not schema:
            raise RuntimeError(f"Missing schema: '{CFG.APP_ID}'")
        self.settings = Gio.Settings.new_full(schema)

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
        win = JankWindow(application=self, settings=self.settings)
        self._async_init = asyncio.create_task(win.initialize())
        self._async_init.add_done_callback(self._async_cleanup)
        win.present()


def main():
    app = JankApplication()
    policy = GLibEventLoopPolicy()
    asyncio.set_event_loop_policy(policy)  # type: ignore
    return app.run(sys.argv)
