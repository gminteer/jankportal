import json
import subprocess
import sys
from typing import TYPE_CHECKING, Any

import gi
import markdown
import requests

from datatypes import DeploymentData

if TYPE_CHECKING:
    from collections.abc import Callable

    from app import JankPortalWindow

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("WebKit", "6.0")

from gi.repository import Adw, Gio, GObject, Gtk, WebKit  # noqa: E402

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

RO = GObject.PARAM_READABLE


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


def create_row(
    deployment: DeploymentData,
    show_changelog: Callable[[Gtk.Button, str], None],
    toggle_ostree_pin: Callable[[Adw.SwitchRow, Any, int], None],
    remove_overlay: Callable[[Gtk.Button, str], None],
):
    """Create expander rows for each deployment"""

    subtitle = ""
    if len(deployment.overlays) > 0:
        subtitle = f"({len(deployment.overlays)} overlaid packages)"
    dep_row = Adw.ExpanderRow(
        title=f"{deployment.index}: Version {deployment.version}", subtitle=subtitle
    )

    # Prefix with icons for currently booted / staged deployments
    icon_box = Gtk.Box(width_request=16)
    if deployment.booted:
        icon = Gtk.Image.new_from_icon_name("system-shutdown-symbolic")
        icon.add_css_class("success")
        icon.props.tooltip_text = "Currently booted"
        icon_box.append(icon)
    elif deployment.staged:
        icon = Gtk.Image.new_from_icon_name("system-reboot-symbolic")
        icon.add_css_class("warning")
        icon.props.tooltip_text = "Staged update (pending reboot)"
        icon_box.append(icon)
    dep_row.add_prefix(icon_box)

    # Suffix with button for changelog
    changelog_btn = Gtk.Button(label="Changelog", css_classes=["action-button"])
    changelog_btn.connect("clicked", show_changelog, deployment.version)
    dep_row.add_suffix(changelog_btn)

    # Add subrow for toggling pinned status
    pin_list = Gtk.ListBox(
        selection_mode=Gtk.SelectionMode.NONE,
        css_classes=["boxed-list", "sub-list"],
    )
    pinned_row = Adw.SwitchRow(title="Pin Deployment", active=deployment.pinned)
    pinned_row.connect("notify::active", toggle_ostree_pin, deployment.index)
    pin_list.append(pinned_row)
    dep_row.add_row(pin_list)

    # Add subrows for overlaid packages with remove buttons if deployment is booted
    if len(deployment.overlays) > 0:
        overlay_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        overlay_box.append(
            Gtk.Label(label="Overlaid Packages", css_classes=["heading"])
        )

        overlay_list = Gtk.ListBox(
            selection_mode=Gtk.SelectionMode.NONE,
            css_classes=["boxed-list", "sub-list"],
        )
        overlay_box.append(overlay_list)

        for overlay in deployment.overlays:
            overlay_row = Adw.ActionRow(title=overlay)
            overlay_list.append(overlay_row)
            if deployment.booted:
                button = Gtk.Button(
                    child=Gtk.Image.new_from_icon_name("edit-delete-symbolic"),
                    css_classes=["action-button", "destructive-action"],
                )
                button.connect("clicked", remove_overlay, overlay)
                overlay_row.add_suffix(button)

        dep_row.add_row(overlay_box)
    return dep_row


def create_page(
    model: Gio.ListStore[DeploymentData],
    current_image: str,
    tag: str,
    row_factory: Callable[[DeploymentData], Adw.ExpanderRow],
):
    container = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, valign=Gtk.Align.START)

    track_widget = Gtk.ListBox(css_classes=["boxed-list", "root-list"])
    filtered_images = [
        image
        for image in IMAGES
        if (
            ("gnome" in image) == ("gnome" in current_image)
            and ("nvidia" in image) == ("nvidia" in current_image)
        )
    ]
    image_model = Gtk.StringList.new(sorted(filtered_images))

    # There's gotta be a better way, maybe?
    index = -1
    for i in range(image_model.get_n_items()):
        if image_model.get_string(i) == current_image:
            index = i
            break
    image_row = Adw.ComboRow(title="Image", model=image_model)
    image_row.set_selected(index)
    track_widget.append(image_row)

    branch_tags, _release_tags = get_tags(current_image)
    tag_model = Gtk.StringList.new(sorted(branch_tags))

    # If there is I don't know it so I'm gonna just caveman my way through marking
    # the active string by value by iterating through the model
    index = -1
    for i in range(tag_model.get_n_items()):
        if tag_model.get_string(i) == tag:
            index = i
            break

    tag_row = Adw.ComboRow(title="Tag", model=tag_model)
    tag_row.set_selected(index)
    track_widget.append(tag_row)
    container.append(track_widget)

    deploy_list = Gtk.ListBox(
        selection_mode=Gtk.SelectionMode.NONE,
        css_classes=["boxed-list", "root-list"],
    )
    deploy_list.bind_model(model, row_factory)
    container.append(deploy_list)

    return Gtk.ScrolledWindow(
        propagate_natural_height=True,
        vscrollbar_policy=Gtk.PolicyType.AUTOMATIC,
        child=container,
    )


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
        uri = f"https://api.github.com/repos/ublue-os/bazzite/releases/tags/{tag}"
        response = requests.get(uri)
        if response.status_code != 200:
            print(f"Error retrieving changelog, received code {response.status_code}")
            return
        raw_changelog = response.json()["body"]

        # Convert to HTML and feed to a WebView
        changelog = markdown.markdown(raw_changelog, extensions=["extra", "codehilite"])
        web_view = WebKit.WebView(width_request=1000, height_request=500)
        web_view.load_html(html_template(changelog))

        # Wrap the WebView in a ToolbarView
        dialog_content = Adw.ToolbarView(content=web_view)
        dialog_content.add_top_bar(
            Adw.HeaderBar(title_widget=Adw.WindowTitle.new("Changes", f"v{tag}"))
        )
        dialog = Adw.Dialog(child=dialog_content, follows_content_size=True)
        dialog.present(self.window)

    def remove_overlay(self, button: Gtk.Button, overlay: str):
        """Send command to remove overlaid package to window's command runner"""

        self.window.command_runner(
            f"Remove {overlay}", f"rpm-ostree uninstall {overlay}"
        )

    def toggle_ostree_pin(self, row: Adw.SwitchRow, gparam_spec: Any, index: int):
        """Send command to pin/unpin deployment to window's command runner"""

        self.window.command_runner(
            f"{'Pin' if row.props.active else 'Unpin'} Deployment {index}",
            f"pkexec ostree admin pin {'' if row.props.active else '--unpin '} {index}",
        )
