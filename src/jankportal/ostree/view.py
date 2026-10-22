"""Build deployments page"""

from typing import TYPE_CHECKING, cast

import gi
import markdown
import requests

from .components import create_page, create_row, search_filterlist
from .models import Deployment, create_deployment_model
from .templates import Changelog

if TYPE_CHECKING:
    from jankportal.window import JankWindow

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("WebKit", "6.0")

from gi.repository import Adw, Gio, GObject, Gtk, WebKit  # noqa: E402

# wait for gobject types or templates break
GObject.type_ensure(WebKit.WebView.__gtype__)  # type: ignore


def wrap_html(changelog: str):
    """Wrap python-markdown generated HTML in a document with github-markdown.css"""

    return f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <link rel="stylesheet"
        href="https://cdnjs.cloudflare.com/ajax/libs/github-markdown-css/5.9.0/github-markdown.min.css"
        integrity="sha512-Ouq1+UcR9ENXndFyd/YA9i+ETLJmX3WoaMBF/nDzdqJbipKGL/SAbkO+qjDoxfD/dhZs4ZqgR9vXkolrK77xmQ=="
        crossorigin="anonymous" referrerpolicy="no-referrer">
</head>
<body class="markdown-body">
    {changelog}
</body>
</html>
"""


class OSTreeView:
    def __init__(self, window: JankWindow):
        """Builds ViewStackPage based on rpm-ostree status, appends to window.stack"""

        self.window = window
        self.window.settings.connect("changed", self.on_settings_changed)

    async def initialize(self):
        def image_filter(image: Gtk.StringObject):
            is_current = image.props.string == self.image
            allow_gnome = self.window.settings.get_boolean("allow-gnome")
            allow_nvidia = self.window.settings.get_boolean("allow-nvidia")
            match_gnome = allow_gnome or ("gnome" in image.props.string) == (
                "gnome" in self.image
            )
            match_nvidia = allow_nvidia or ("nvidia" in image.props.string) == (
                "nvidia" in self.image
            )
            return is_current or (match_gnome and match_nvidia)

        def tag_filter(tag: Gtk.StringObject):
            is_current = tag.props.string == self.tag
            return is_current or ("." not in tag.props.string)

        def row_factory(deployment: Deployment):
            return create_row(
                deployment,
                self.on_changelog_clicked,
                self.on_pinned_activated,
                self.on_remove_clicked,
                self.on_rebase_activated,
            )

        self.model, self.image, self.tag = await create_deployment_model(
            self.window.panic
        )
        self._image_filter = Gtk.CustomFilter.new(image_filter)
        self._tag_filter = Gtk.CustomFilter.new(tag_filter)
        self.page = await create_page(
            self.model,
            self.image,
            self.tag,
            row_factory,
            self._image_filter,
            self._tag_filter,
            self.window.panic,
        )

        img_model = cast("Gtk.FilterListModel", self.page.image.props.model)
        self._image_index = search_filterlist(img_model, self.image)
        tag_model = cast("Gtk.FilterListModel", self.page.tag.props.model)
        self._tag_index = search_filterlist(tag_model, self.tag)

        self.page.img_rebase.connect("activated", self.on_img_rebase_activated)
        self.page.img_reset.connect("activated", self.on_img_reset_activated)
        self.page.img_update.connect("activated", self.on_img_update_activated)
        self.page.image.connect("notify::selected-item", self.on_image_selected)
        self.page.tag.connect("notify::selected-item", self.on_tag_selected)
        placeholder = cast("Adw.Bin", self.window.stack.get_child_by_name("ostree"))
        placeholder.props.child = self.page

    @property
    def selected_image(self):
        return cast(
            "Gtk.StringObject", self.page.image.get_selected_item()
        ).get_string()

    @property
    def selected_tag(self):
        return cast("Gtk.StringObject", self.page.tag.get_selected_item()).get_string()

    def on_settings_changed(self, settings: Gio.Settings, key: str):
        if key in ["allow-gnome", "allow-nvidia"]:
            self._image_filter.changed(Gtk.FilterChange.DIFFERENT)

    def on_img_rebase_activated(self, button_row: Adw.ButtonRow):
        self.window.command_runner(
            title="Rebase",
            script=f"brh rebase {self.selected_image}:{self.selected_tag}",
        )

    def on_img_reset_activated(self, button_row: Adw.ButtonRow):
        self.page.image.set_selected(self._image_index)
        self.page.tag.set_selected(self._tag_index)

    def on_img_update_activated(self, action_row: Adw.ActionRow):
        self.window.command_runner(title="System Update", script="ujust update")

    def _handle_img_action_visibility(self):
        visible = (self.image != self.selected_image) or (self.tag != self.selected_tag)
        self.page.img_rebase.props.visible = visible
        self.page.img_reset.props.visible = visible

    def on_image_selected(
        self, drop_down: Gtk.DropDown, g_param_spec: GObject.ParamSpec
    ):
        self._handle_img_action_visibility()

    def on_tag_selected(self, drop_down: Gtk.DropDown, g_param_spec: GObject.ParamSpec):
        self._handle_img_action_visibility()

    def on_changelog_clicked(self, button: Gtk.Button, tag: str):
        """Show changelog in an AdwDialog overlay"""

        # Get release notes for whichever version was selected
        # and convert to an HTML document
        response = requests.get(
            f"https://api.github.com/repos/ublue-os/bazzite/releases/tags/{tag}"
        )
        if response.status_code != 200:
            self.window.warn(
                title=f"HTTP Error {response.status_code}", message=response.text
            )
            return
        changelog = wrap_html(
            markdown.markdown(
                response.json()["body"], extensions=["extra", "codehilite"]
            )
        )
        dialog = Changelog()
        dialog.bar.props.subtitle = f"v{tag}"
        dialog.web_view.load_html(changelog)
        dialog.present(self.window)

    def on_rebase_activated(self, row: Adw.ActionRow, image: str, version: str):
        self.window.command_runner(
            title="Rebase", script=f"brh rebase {image}-{version}"
        )

    def on_remove_clicked(self, button: Gtk.Button, overlay: str):
        """Send command to remove overlaid package to window's command runner"""

        self.window.command_runner(
            f"Remove {overlay}", f"rpm-ostree uninstall {overlay}"
        )

    def on_pinned_activated(
        self, row: Adw.SwitchRow, g_param_spec: GObject.ParamSpec, index: int
    ):
        """Send command to pin/unpin deployment to window's command runner"""

        self.window.command_runner(
            f"{'Pin' if row.props.active else 'Unpin'} Deployment {index}",
            f"pkexec ostree admin pin {'' if row.props.active else '--unpin '} {index}",
        )
