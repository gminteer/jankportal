"""High-level GTK / Python application housekeeping stuff"""

import asyncio
import sys
import tempfile
from importlib import resources
from typing import cast

import gi
from gi.events import GLibEventLoopPolicy

from . import _config as CFG

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

# load settings schema
with resources.path(CFG.APP_NAME) as app_path:
    schema_source = Gio.SettingsSchemaSource.new_from_directory(
        str(app_path),
        parent=Gio.SettingsSchemaSource.get_default(),
        trusted=False,
    )
    schema = schema_source.lookup(CFG.APP_ID, recursive=False)

# load resources
resource_blob = (
    resources.files(CFG.APP_NAME).joinpath(f"{CFG.APP_NAME}.gresource").read_bytes()
)
resource = Gio.Resource.new_from_data(GLib.Bytes.new(resource_blob))
Gio.resources_register(resource)
font_blob = cast(
    "bytes",
    Gio.resources_lookup_data(
        f"{CFG.APP_PATH}/font/promptfont.ttf", Gio.ResourceLookupFlags.NONE
    ).get_data(),
)
# you apparently can't just give Pango a bytestream
with tempfile.NamedTemporaryFile(suffix=".ttf") as temp:
    temp.write(font_blob)
    font_map = PangoCairo.font_map_get_default()
    font_map.add_font_file(temp.name)

from .window import JankWindow  # noqa: E402


class JankApplication(Adw.Application):
    """Application"""

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
