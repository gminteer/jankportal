from typing import TYPE_CHECKING, cast

import gi

from jankportal.lib import align_drop_down

from .models import Deployment, create_tag_model
from .templates import DeploymentActions, OverlayList, OverlayPill, Page, Row

if TYPE_CHECKING:
    from collections.abc import Callable

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gio, GObject, Gtk  # noqa: E402

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


def create_row(
    deployment: Deployment,
    on_changelog_clicked: Callable[[Gtk.Button, str], None],
    on_pinned_active: Callable[[Adw.SwitchRow, GObject.ParamSpec, int], None],
    on_remove_clicked: Callable[[Gtk.Button, str], None],
    on_rebase_activated: Callable[[Adw.ActionRow, str, str], None],
    on_reset_activated: Callable[[Adw.ActionRow], None],
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
    deployment.bind_property(
        source_property="pinned",
        target=actions.pin,
        target_property="active",
        flags=GObject.BindingFlags.SYNC_CREATE,
    )
    actions.pin.connect("notify::active", on_pinned_active, deployment.index)
    actions.rebase.connect(
        "activated", on_rebase_activated, deployment.image, deployment.version
    )
    deployment.bind_property(
        source_property="booted",
        target=actions.reset,
        target_property="visible",
        flags=GObject.BindingFlags.SYNC_CREATE,
    )
    actions.reset.connect("activated", on_reset_activated)
    row.add_row(actions)

    # Add subrows for overlaid packages with remove buttons if deployment is booted
    if len(deployment.overlays) > 0:
        overlays = OverlayList()

        for overlay in deployment.overlays:
            pill = OverlayPill()
            pill.label.props.label = overlay
            pill.remove_btn.connect("clicked", on_remove_clicked, overlay)
            deployment.bind_property(
                source_property="booted",
                target=pill.remove_btn,
                target_property="visible",
                flags=GObject.BindingFlags.SYNC_CREATE,
            )
            overlays.box.append(pill)

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

    image_filter_model = Gtk.FilterListModel.new(IMAGES, image_filter)
    page.image.set_model(image_filter_model)
    index = search_filterlist(image_filter_model, current_image)
    if index == -1:
        panic(f"'{current_image}' not in filtered image list!")
    page.image.set_selected(index)

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
