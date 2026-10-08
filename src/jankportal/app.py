import asyncio
import sys
import tempfile
from importlib.resources import files

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

# load resources
resource_blob = files(CFG.APP_NAME).joinpath(f"{CFG.APP_NAME}.gresource").read_bytes()
resource = Gio.Resource.new_from_data(GLib.Bytes.new(resource_blob))
Gio.resources_register(resource)
font_blob = Gio.resources_lookup_data(
    f"{CFG.APP_PATH}/font/promptfont.ttf", Gio.ResourceLookupFlags.NONE
).get_data()
if font_blob:  # I wonder if i should invert this and blow up if it fails?
    with tempfile.NamedTemporaryFile(suffix=".ttf") as temp:
        temp.write(font_blob)  # you apparently can't just give Pango a bytestream
        font_map = PangoCairo.font_map_get_default()
        font_map.add_font_file(temp.name)

from .window import JankWindow  # noqa: E402


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
