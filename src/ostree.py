import json
import subprocess
import sys
from typing import TYPE_CHECKING, Any, TypedDict

import gi
import markdown
import requests

if TYPE_CHECKING:
    from app import JankPortalWindow

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("WebKit", "6.0")

from gi.repository import Adw, Gio, GObject, Gtk, WebKit  # noqa: E402

RO = GObject.PARAM_READABLE


DeploymentType = TypedDict(
    "DeploymentType",
    {
        "container-image-reference": str,
        "version": str,
        "pinned": bool,
        "booted": bool,
        "staged": bool,
        "packages": list[str],
        "requested-local-packages": list[str],
    },
)
"""Schema for JSON returned by rpm-ostree status (partial)"""


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


class DeploymentData(GObject.Object):
    """GObject adapter for DeploymentType"""

    __gtype_name__ = "DeploymentData"

    def __init__(self, index: int, deployment: DeploymentType, **kwargs: Any):
        super().__init__(**kwargs)
        self._data = deployment
        self._index = index
        self._overlays = [
            *deployment["packages"],
            *deployment["requested-local-packages"],
        ]

    @GObject.Property(type=int, default=0, flags=RO)
    def index(self):
        return self._index

    @GObject.Property(type=str, default="", flags=RO)
    def edition(self):
        return self._data["container-image-reference"].split("/")[-1]

    @GObject.Property(type=str, default="", flags=RO)
    def version(self):
        return self._data["version"]

    @GObject.Property(type=bool, default=False, flags=RO)
    def pinned(self):
        return self._data["pinned"]

    @GObject.Property(type=bool, default=False, flags=RO)
    def booted(self):
        return self._data["booted"]

    @GObject.Property(type=bool, default=False, flags=RO)
    def staged(self):
        return self._data["staged"]

    @property
    def overlays(self):
        return self._overlays


class OSTreeUI:
    def __init__(self, window: JankPortalWindow):
        """Builds ViewStackPage based on rpm-ostree status, appends to window.stack"""

        self.window = window
        self.model = self._create_model()

        container = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL, valign=Gtk.Align.START
        )

        container.append(
            Gtk.Label(label="Current system deployments", css_classes=["heading"])
        )

        deploy_list = Gtk.ListBox(
            selection_mode=Gtk.SelectionMode.NONE,
            css_classes=["boxed-list", "root-list"],
        )
        deploy_list.bind_model(self.model, self.create_row)
        container.append(deploy_list)

        scrollable = Gtk.ScrolledWindow(
            propagate_natural_height=True,
            vscrollbar_policy=Gtk.PolicyType.AUTOMATIC,
            child=container,
        )
        self.window.stack.add_titled(
            child=scrollable, title="Deployments", name="ostree"
        )

    def _create_model(self):
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
            for index, deployment in enumerate(ostree_status["deployments"]):
                model.append(DeploymentData(index=index, deployment=deployment))
            return model

        except FileNotFoundError:
            print("rpm-ostree not in $PATH", file=sys.stderr)
            sys.exit(1)

        except subprocess.CalledProcessError as error:
            print(f"rpm-ostree error: {error.stderr}")
            sys.exit(1)

    def create_row(self, deployment: DeploymentData):
        """Create expander rows for each deployment"""

        subtitle = deployment.version
        if len(deployment.overlays) > 0:
            subtitle += f" ({len(deployment.overlays)} overlaid packages)"
        dep_row = Adw.ExpanderRow(
            title=f"{deployment.index}: {deployment.edition}", subtitle=subtitle
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
        changelog_btn.connect("clicked", self.show_changelog, deployment.version)
        dep_row.add_suffix(changelog_btn)

        # Add subrow for toggling pinned status
        pin_list = Gtk.ListBox(
            selection_mode=Gtk.SelectionMode.NONE,
            css_classes=["boxed-list", "sub-list"],
        )
        pinned_row = Adw.SwitchRow(title="Pin Deployment", active=deployment.pinned)
        pinned_row.connect("notify::active", self.toggle_ostree_pin, deployment.index)
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
                    content = Adw.ButtonContent(
                        label="Remove", icon_name="edit-delete-symbolic"
                    )
                    button = Gtk.Button(
                        child=content,
                        css_classes=["action-button", "destructive-action"],
                    )
                    button.connect("clicked", self.remove_overlay, overlay)
                    overlay_row.add_suffix(button)

            dep_row.add_row(overlay_box)
        return dep_row

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
