import json
import subprocess
import sys
from typing import TYPE_CHECKING

import gi
import markdown
import requests

from .lib import RES_PATH, DeploymentData

if TYPE_CHECKING:
    from collections.abc import Callable

    from .app import JankPortalWindow

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("WebKit", "6.0")

from gi.repository import Adw, Gio, GObject, Gtk, WebKit  # noqa: E402

GObject.type_ensure(WebKit.WebView.__gtype__)  # type: ignore

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


def create_model():
    """Parse rpm-ostree status into Gio.ListStore"""
    try:
        model = Gio.ListStore(item_type=DeploymentData)
        result = subprocess.run(
            ["rpm-ostree", "status", "--json"],
            capture_output=True,
            text=True,
            check=True,
        )
        ostree_status = json.loads(result.stdout)

        image: str = ""
        tag: str = ""
        for index, deployment in enumerate(ostree_status["deployments"]):
            model.append(DeploymentData(index=index, deployment=deployment))
            if deployment["booted"]:
                image, tag = (
                    deployment["container-image-reference"].split("/")[-1].split(":")
                )
        return model, image, tag

    except FileNotFoundError:
        print("rpm-ostree not in $PATH", file=sys.stderr)
        sys.exit(1)

    except subprocess.CalledProcessError as error:
        print(f"rpm-ostree error: {error.stderr}", file=sys.stderr)
        sys.exit(1)


def html_template(changelog: str):
    """Wrap python-markdown generated HTML in an document with github-markdown.css"""

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


def get_tags(image: str) -> tuple[list[str], list[str]]:
    """Get tags for a given image from skopeo, sorts them into branches and releases"""

    image_uri = f"docker://ghcr.io/ublue-os/{image}"
    try:
        result = subprocess.run(
            ["skopeo", "list-tags", image_uri],
            capture_output=True,
            text=True,
            check=True,
        )
        raw_tags = json.loads(result.stdout)["Tags"]
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
        print("skopeo not in $PATH", file=sys.stderr)
        sys.exit(1)

    except subprocess.CalledProcessError as error:
        print(f"skopeo error: {error.stderr}", file=sys.stderr)
        sys.exit(1)


@Gtk.Template(resource_path=f"{RES_PATH}/ostree/row.ui")
class OSTreeRow(Adw.ExpanderRow):
    __gtype_name__ = "OSTreeRow"
    icon_box: Gtk.Box = Gtk.Template.Child()
    changelog: Gtk.Button = Gtk.Template.Child()


@Gtk.Template(resource_path=f"{RES_PATH}/ostree/pin_list.ui")
class OSTreePinList(Gtk.ListBox):
    __gtype_name__ = "OSTreePinList"
    pinned: Adw.SwitchRow = Gtk.Template.Child()


@Gtk.Template(resource_path=f"{RES_PATH}/ostree/overlay_list.ui")
class OSTreeOverlayList(Gtk.Box):
    __gtype_name__ = "OSTreeOverlayList"
    list: Gtk.ListBox = Gtk.Template.Child()


@Gtk.Template(resource_path=f"{RES_PATH}/ostree/page.ui")
class OSTreePage(Gtk.ScrolledWindow):
    __gtype_name__ = "OSTreePage"
    container: Gtk.Box = Gtk.Template.Child()
    image: Adw.ComboRow = Gtk.Template.Child()
    tag: Adw.ComboRow = Gtk.Template.Child()


def create_row(
    deployment: DeploymentData,
    show_changelog: Callable[[Gtk.Button, str], None],
    toggle_ostree_pin: Callable[[Adw.SwitchRow, GObject.ParamSpec, int], None],
    remove_overlay: Callable[[Gtk.Button, str], None],
):
    """Create expander rows for each deployment"""

    row = OSTreeRow()
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

    row.changelog.connect("clicked", show_changelog, deployment.version)

    # Add subrow for toggling pinned status
    pin = OSTreePinList()
    pin.pinned.connect("notify::active", toggle_ostree_pin, deployment.index)
    row.add_row(pin)

    # Add subrows for overlaid packages with remove buttons if deployment is booted
    if len(deployment.overlays) > 0:
        overlays = OSTreeOverlayList()

        for overlay in deployment.overlays:
            overlay_row = Adw.ActionRow(title=overlay)
            overlays.list.append(overlay_row)
            if deployment.booted:
                button = Gtk.Button(
                    child=Gtk.Image.new_from_icon_name("edit-delete-symbolic"),
                    css_classes=["action-button", "destructive-action"],
                )
                button.connect("clicked", remove_overlay, overlay)
                overlay_row.add_suffix(button)

        row.add_row(overlays)
    return row


def find_in_string_list(model: Gtk.StringList, string: str):
    for i in range(model.get_n_items()):
        if model.get_string(i) == string:
            return i
    return -1


def create_page(
    model: Gio.ListStore[DeploymentData],
    current_image: str,
    current_tag: str,
    row_factory: Callable[[DeploymentData], Adw.ExpanderRow],
):
    page = OSTreePage()

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
    if index := find_in_string_list(image_model, current_image):
        page.image.set_selected(index)
    else:
        image_model.append(current_image)
        page.image.set_selected(image_model.get_n_items())
    # Only show branch tags
    branch_tags, _release_tags = get_tags(current_image)
    tag_model = Gtk.StringList.new(sorted(branch_tags))

    page.tag.set_model(tag_model)
    if index := find_in_string_list(tag_model, current_tag):
        page.tag.set_selected(index)
    else:
        tag_model.append(current_tag)
        page.tag.set_selected(tag_model.get_n_items())

    deploy_list = Gtk.ListBox(
        selection_mode=Gtk.SelectionMode.NONE,
        css_classes=["boxed-list", "root-list"],
    )
    deploy_list.bind_model(model, row_factory)
    page.container.append(deploy_list)

    return page


@Gtk.Template(resource_path=f"{RES_PATH}/ostree/changelog_dialog.ui")
class ChangelogDialog(Adw.Dialog):
    __gtype_name__ = "ChangelogDialog"
    bar: Adw.WindowTitle = Gtk.Template.Child()
    web_view: WebKit.WebView = Gtk.Template.Child()


class OSTreeUI:
    def __init__(self, window: JankPortalWindow):
        """Builds ViewStackPage based on rpm-ostree status, appends to window.stack"""

        self.window = window
        self.model, image, tag = create_model()

        def row_factory(deployment: DeploymentData):
            return create_row(
                deployment,
                self.show_changelog,
                self.toggle_ostree_pin,
                self.remove_overlay,
            )

        page = create_page(self.model, image, tag, row_factory)
        self.window.stack.add_titled(child=page, title="Deployments", name="ostree")

    def show_changelog(self, button: Gtk.Button, tag: str):
        """Show changelog in an AdwDialog overlay"""

        # Get release notes for whichever version was selected
        # and convert to an HTML document
        uri = f"https://api.github.com/repos/ublue-os/bazzite/releases/tags/{tag}"
        response = requests.get(uri)
        if response.status_code != 200:
            self.window.show_error(
                f"Error retrieving changelog, received code {response.status_code}"
            )
            return
        raw_changelog = response.json()["body"]
        changelog = html_template(
            markdown.markdown(raw_changelog, extensions=["extra", "codehilite"])
        )
        dialog = ChangelogDialog()
        dialog.bar.props.subtitle = f"v{tag}"
        dialog.web_view.load_html(changelog)
        dialog.present(self.window)

    def remove_overlay(self, button: Gtk.Button, overlay: str):
        """Send command to remove overlaid package to window's command runner"""

        self.window.command_runner(
            f"Remove {overlay}", f"rpm-ostree uninstall {overlay}"
        )

    def toggle_ostree_pin(
        self, row: Adw.SwitchRow, g_param_spec: GObject.ParamSpec, index: int
    ):
        """Send command to pin/unpin deployment to window's command runner"""

        self.window.command_runner(
            f"{'Pin' if row.props.active else 'Unpin'} Deployment {index}",
            f"pkexec ostree admin pin {'' if row.props.active else '--unpin '} {index}",
        )
