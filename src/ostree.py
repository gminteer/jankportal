import json
import subprocess
import sys
from typing import TYPE_CHECKING, Any, TypedDict

import gi

if TYPE_CHECKING:
    from app import JankPortalWindow

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gio, GObject, Gtk  # noqa: E402

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

        title = Gtk.Label(label="Current system deployments")
        title.add_css_class("heading")
        container.append(title)

        boxed_list = Gtk.ListBox(selection_mode=Gtk.SelectionMode.NONE)
        boxed_list.add_css_class("boxed-list")
        boxed_list.add_css_class("root-list")
        boxed_list.bind_model(self.model, self.create_row)
        container.append(boxed_list)

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

        subtitle = (
            f"{deployment.version} ({'not ' if not deployment.pinned else ''}pinned)"
        )
        if len(deployment.overlays) > 0:
            subtitle += f" ({len(deployment.overlays)} overlaid packages)"
        row = Adw.ExpanderRow(
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
        row.add_prefix(icon_box)

        # Add subrow for toggling pinned status
        pin_list = Gtk.ListBox(selection_mode=Gtk.SelectionMode.NONE)
        pin_list.add_css_class("boxed-list")
        pin_list.add_css_class("sub-list")
        pinned_row = Adw.SwitchRow(title="Pin Deployment", active=deployment.pinned)
        pinned_row.connect("notify::active", self.toggle_ostree_pin, deployment.index)
        pin_list.append(pinned_row)
        row.add_row(pin_list)

        # Add subrows for overlaid packages with remove buttons
        if len(deployment.overlays) > 0:
            overlay_container = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)

            title = Gtk.Label(label="Overlaid Packages")
            title.add_css_class("heading")
            overlay_container.append(title)

            overlay_list = Gtk.ListBox(selection_mode=Gtk.SelectionMode.NONE)
            overlay_list.add_css_class("boxed-list")
            overlay_list.add_css_class("sub-list")
            overlay_container.append(overlay_list)

            for overlay in deployment.overlays:
                overlay_row = Adw.ActionRow(title=overlay)
                overlay_list.append(overlay_row)
                content = Adw.ButtonContent(
                    label="Remove", icon_name="edit-delete-symbolic"
                )
                button = Gtk.Button(child=content)
                button.add_css_class("destructive-action")
                button.add_css_class("action-button")
                button.connect(
                    "clicked", self.remove_overlay, deployment.index, overlay
                )
                overlay_row.add_suffix(button)

            row.add_row(overlay_container)
        return row

    def remove_overlay(self, button: Gtk.Button, deployment: str, overlay: str):
        """Send command to remove overlaid package to window's command runner"""

        print(f"I should remove {overlay} in deployment {deployment}")

    def toggle_ostree_pin(self, row: Adw.SwitchRow, gparam_spec: Any, index: int):
        """Send command to pin/unpin deployment to window's command runner"""

        action = "pin" if row.props.active else "unpin"
        print(f"I should {action} index {index}")
