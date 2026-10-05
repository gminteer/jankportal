import asyncio
import json
import sys
from typing import TYPE_CHECKING, cast

import gi
import markdown
import requests

from jankportal.lib import align_drop_down

from .models import Deployment
from .templates import Changelog, DeploymentActions, OverlayList, Page, Row

if TYPE_CHECKING:
    from collections.abc import Callable

    from jankportal.app import JankPortalWindow

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("WebKit", "6.0")

from gi.repository import Adw, Gio, GLib, GObject, Gtk, WebKit  # noqa: E402

# Wait for WebKit to resolve
GObject.type_ensure(WebKit.WebView.__gtype__)  # type: ignore


# Constants
IMAGES = [
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


# Helper functions
async def create_model(panic: Callable[[str], None]):
    """Parse rpm-ostree status into Gio.ListStore"""
    try:
        model = Gio.ListStore(item_type=Deployment)
        process = await asyncio.create_subprocess_exec(
            "rpm-ostree",
            "status",
            "--json",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await process.communicate()

        if process.returncode != 0:
            panic(f"rpm-ostree error: {stderr}")
        ostree_status = json.loads(stdout)

        image: str = ""
        tag: str = ""
        for index, deployment in enumerate(ostree_status["deployments"]):
            model.append(Deployment(index=index, deployment=deployment))
            if deployment["booted"]:
                image, tag = (
                    deployment["container-image-reference"].split("/")[-1].split(":")
                )
        return model, image, tag

    except FileNotFoundError:
        panic("rpm-ostree not in $PATH")
        sys.exit(1)  # Never reached, makes type analysis happy


async def get_tags(
    image: str, panic: Callable[[str], None]
) -> tuple[list[str], list[str]]:
    """Get tags for a given image from skopeo, sorts them into branches and releases"""

    image_uri = f"docker://ghcr.io/ublue-os/{image}"
    try:
        process = await asyncio.create_subprocess_exec(
            "skopeo",
            "list-tags",
            image_uri,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await process.communicate()
        if process.returncode != 0:
            panic(f"skopeo error: {stderr}")

        raw_tags = json.loads(stdout)["Tags"]
        # filter for just stable and testing tags
        tags = [tag for tag in raw_tags if tag.startswith(("stable", "testing"))]
        branch_tags: list[str] = []
        release_tags: list[str] = []
        for tag in tags:
            if "." in tag:
                release_tags.append(tag)
            else:
                branch_tags.append(tag)
        return branch_tags, release_tags

    except FileNotFoundError:
        panic("skopeo not in $PATH")
        sys.exit(1)  # Never reaced, makes type analysis happy


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
    panic: Callable[[str], None],
):
    page = Page()
    align_drop_down(page.image)
    align_drop_down(page.tag)

    # Prevent users from going off the rails
    # (only show nvidia/gnome images if currently on a matching image)
    filtered_images = [
        image
        for image in IMAGES
        if (
            ("gnome" in image) == ("gnome" in current_image)
            and ("nvidia" in image) == ("nvidia" in current_image)
        )
    ]
    image_model = Gtk.StringList.new(sorted(filtered_images))

    page.image.set_model(image_model)
    index = image_model.find(current_image)
    if index == GLib.MAXUINT:
        image_model.append(current_image)
        page.image.set_selected(len(image_model))
    else:
        page.image.set_selected(index)

    # Only show branch tags
    branch_tags, _release_tags = await get_tags(current_image, panic)
    tag_model = Gtk.StringList.new(sorted(branch_tags))

    page.tag.set_model(tag_model)
    index = tag_model.find(current_tag)
    if index == GLib.MAXUINT:
        tag_model.append(current_tag)
        page.tag.set_selected(tag_model.get_n_items())
    else:
        page.tag.set_selected(index)

    deploy_list = Gtk.ListBox(
        selection_mode=Gtk.SelectionMode.NONE,
        css_classes=["boxed-list", "root-list"],
    )
    deploy_list.bind_model(model, row_factory)
    page.container.append(deploy_list)

    return page


class OSTreeView:
    def __init__(self, window: JankPortalWindow):
        """Builds ViewStackPage based on rpm-ostree status, appends to window.stack"""

        self.window = window

    async def initialize(self):
        self.model, self.image, self.tag = await create_model(self.window.panic)

        def row_factory(deployment: Deployment):
            return create_row(
                deployment,
                self.on_changelog_clicked,
                self.on_pinned_activated,
                self.on_remove_clicked,
                self.on_rebase_activated,
            )

        self.page = await create_page(
            self.model, self.image, self.tag, row_factory, self.window.panic
        )
        self._image_index = cast("Gtk.StringList", self.page.image.props.model).find(
            self.image
        )

        self._tag_index = cast("Gtk.StringList", self.page.tag.props.model).find(
            self.tag
        )
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
