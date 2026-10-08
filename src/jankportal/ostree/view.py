from typing import TYPE_CHECKING, cast

import gi
import markdown
import requests

from jankportal.lib import align_drop_down

from .models import Deployment, create_deployment_model, create_tag_model
from .templates import Changelog, DeploymentActions, OverlayList, Page, Row

if TYPE_CHECKING:
    from collections.abc import Callable

    from jankportal.app import JankWindow

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("WebKit", "6.0")

from gi.repository import Adw, Gio, GObject, Gtk, WebKit  # noqa: E402

# wait for gobject types or templates break
GObject.type_ensure(WebKit.WebView.__gtype__)  # type: ignore


IMAGES = Gtk.StringList.new(
    [
        "bazzite",
        "bazzite-deck",
        "bazzite-nvidia",
        "bazzite-nvidia-open",
        "bazzite-deck-nvidia",
        "bazzite-gnome",
        "bazzite-gnome-nvidia-open",
        "bazzite-deck-gnome",
        "bazzite-dx",
        "bazzite-dx-gnome",
        "bazzite-dx-nvidia",
        "bazzite-dx-nvidia-gnome",
    ]
)


def search_filterlist(list: Gtk.FilterListModel, val: str):
    index = -1
    for i in range(len(list)):
        current = cast("Gtk.StringObject", list.get_item(i))
        if current.props.string == val:
            index = i
            break
    return index


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


# Component builders
def create_row(
    deployment: Deployment,
    on_changelog_clicked: Callable[[Gtk.Button, str], None],
    on_pinned_active: Callable[[Adw.SwitchRow, GObject.ParamSpec, int], None],
    on_remove_clicked: Callable[[Gtk.Button, str], None],
    on_rebase_activated: Callable[[Adw.ActionRow, str, str], None],
):
    """Create expander rows for each deployment"""

    row = Row()
    row.props.title = f"{deployment.index}: Version {deployment.version}"
    if len(deployment.overlays) > 0:
        row.props.subtitle = f"({len(deployment.overlays)} overlaid packages)"

    if deployment.booted:
        icon = Gtk.Image.new_from_icon_name("system-shutdown-symbolic")
        icon.add_css_class("success")
        icon.props.tooltip_text = "Currently booted"
        row.icon_box.append(icon)
    elif deployment.staged:
        icon = Gtk.Image.new_from_icon_name("system-reboot-symbolic")
        icon.add_css_class("warning")
        icon.props.tooltip_text = "Staged update (pending reboot)"
        row.icon_box.append(icon)

    row.changelog.connect("clicked", on_changelog_clicked, deployment.version)

    # Add subrows for deployment actions
    actions = DeploymentActions()
    actions.pin.connect("notify::active", on_pinned_active, deployment.index)
    actions.rebase.connect(
        "activated", on_rebase_activated, deployment.image, deployment.version
    )
    row.add_row(actions)

    # Add subrows for overlaid packages with remove buttons if deployment is booted
    if len(deployment.overlays) > 0:
        overlays = OverlayList()

        for overlay in deployment.overlays:
            overlay_row = Adw.ActionRow(title=overlay)
            overlays.list.append(overlay_row)
            if deployment.booted:
                button = Gtk.Button(
                    child=Gtk.Image.new_from_icon_name("edit-delete-symbolic"),
                    css_classes=["action-button", "destructive-action"],
                )
                button.connect("clicked", on_remove_clicked, overlay)
                overlay_row.add_suffix(button)

        row.add_row(overlays)
    return row


async def create_page(
    model: Gio.ListStore[Deployment],
    current_image: str,
    current_tag: str,
    row_factory: Callable[[Deployment], Adw.ExpanderRow],
    image_filter: Gtk.CustomFilter,
    tag_filter: Gtk.CustomFilter,
    panic: Callable[[str], None],
):
    def on_img_list_keynav_failed(listbox: Gtk.ListBox, direction: Gtk.DirectionType):
        if direction in [
            Gtk.DirectionType.DOWN,
            Gtk.DirectionType.RIGHT,
            Gtk.DirectionType.TAB_FORWARD,
        ]:
            return deploy_list.child_focus(direction)
        return False

    def on_deploy_list_keynav_failed(
        listbox: Gtk.ListBox, direction: Gtk.DirectionType
    ):
        if direction in [
            Gtk.DirectionType.UP,
            Gtk.DirectionType.LEFT,
            Gtk.DirectionType.TAB_BACKWARD,
        ]:
            return page.img_list.child_focus(direction)
        return False

    page = Page()
    align_drop_down(page.image)
    align_drop_down(page.tag)

    # Prevent users from going off the rails
    # (only show nvidia/gnome images if currently on a matching image)
    image_filter_model = Gtk.FilterListModel.new(IMAGES, image_filter)
    page.image.set_model(image_filter_model)
    index = search_filterlist(image_filter_model, current_image)
    if index == -1:
        panic(f"'{current_image}' not in filtered image list!")
    page.image.set_selected(index)

    # Only show branch tags
    tags = await create_tag_model(current_image, panic)
    tag_filter_model = Gtk.FilterListModel.new(tags, tag_filter)

    page.tag.set_model(tag_filter_model)
    index = search_filterlist(tag_filter_model, current_tag)
    if index == -1:
        panic(f"'{current_tag}' not in filtered tag list!")
    page.tag.set_selected(index)

    deploy_list = Gtk.ListBox(
        selection_mode=Gtk.SelectionMode.NONE,
        css_classes=["boxed-list", "root-list"],
    )
    deploy_list.bind_model(model, row_factory)
    page.container.append(deploy_list)
    page.img_list.connect("keynav-failed", on_img_list_keynav_failed)
    deploy_list.connect("keynav-failed", on_deploy_list_keynav_failed)
    return page


class OSTreeView:
    def __init__(self, window: JankWindow):
        """Builds ViewStackPage based on rpm-ostree status, appends to window.stack"""

        self.window = window

    async def initialize(self):
        def image_filter(image: Gtk.StringObject):
            is_current = image.props.string == self.image
            match_gnome = ("gnome" in image.props.string) == ("gnome" in self.image)
            match_nvidia = ("nvidia" in image.props.string) == ("nvidia" in self.image)
            return (match_gnome and match_nvidia) or is_current

        def tag_filter(tag: Gtk.StringObject):
            is_current = tag.props.string == self.tag
            return ("." not in tag.props.string) or is_current

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

    def on_img_rebase_activated(self, button_row: Adw.ButtonRow):
        self.window.command_runner(
            title="Rebase",
            script=f"brh rebase {self.selected_image}:{self.selected_tag}",
        )

    def on_img_reset_activated(self, button_row: Adw.ButtonRow):
        self.page.image.set_selected(self._image_index)
        self.page.tag.set_selected(self._tag_index)

    def _handle_img_action_visibility(self):
        visible = not (
            self.image == self.selected_image and self.tag == self.selected_tag
        )
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
        uri = f"https://api.github.com/repos/ublue-os/bazzite/releases/tags/{tag}"
        response = requests.get(uri)
        if response.status_code != 200:
            self.window.warn(
                title=f"HTTP Error {response.status_code}", message=response.text
            )
            return
        raw_changelog = response.json()["body"]
        changelog = wrap_html(
            markdown.markdown(raw_changelog, extensions=["extra", "codehilite"])
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
