"""Create different types of action rows"""

from typing import TYPE_CHECKING, cast

import gi

from jankportal.lib import align_drop_down

from .models import Option

if TYPE_CHECKING:
    from collections.abc import Callable

    from .models import Action

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, GObject, Gtk  # noqa: E402


def create_emblem(type: str, description: str = ""):
    """Make no status emblem for rows with options, but no status script"""
    icon = None
    match type:
        case "NO_STATUS":
            icon = Gtk.Image.new_from_icon_name("emblem-important-symbolic")
            icon.add_css_class("warning")
            icon.props.tooltip_text = "No status provided"
        case "NOT_A_DECK":
            icon = Gtk.Image.new_from_icon_name("dialog-information-symbolic")
            icon.add_css_class("warning")
            icon.props.tooltip_text = "For handhelds and HTPCs only"
        case "NOT_FOUND":
            icon = Gtk.Image.new_from_icon_name("xsi-dialog-error-symbolic")
            icon.add_css_class("error")
            icon.props.tooltip_text = f"Status command '{description}' not found"
        case "ERROR":
            icon = Gtk.Image.new_from_icon_name("xsi-dialog-error-symbolic")
            icon.add_css_class("error")
            icon.props.tooltip_text = description or "No details provided"

        case _:
            pass
    return icon


def on_status_changed(
    action: Action,
    g_param_spec: GObject.ParamSpec,
    emblem_box: Gtk.Box,
    action_box: Gtk.Box | None = None,
):
    """Update action emblem on status change"""
    while (child := emblem_box.get_first_child()) is not None:
        emblem_box.remove(child)
    if action.status.isupper():
        emblem = create_emblem(action.status, action.status_detail or "")
        if emblem:
            emblem_box.append(emblem)
        if action.status == "NOT_A_DECK" and isinstance(action_box, Gtk.Box):
            action_box.props.visible = False
            # if we hide the buttons we need to make the row navigable to not make
            # directional focus shift hit a brick wall
            row = action_box.get_ancestor(Adw.ActionRow)
            if row:
                row.props.focusable = True


def create_expander_row(
    action: Action,
    callback: Callable[[Gtk.Widget, str, str, Callable[[], None] | None], None],
):
    """Create an ExpanderRow with ActionRows"""
    row = Adw.ExpanderRow(title=action.title, subtitle=action.description)
    emblem_box = Gtk.Box(width_request=16, name="emblem-box")
    row.add_suffix(emblem_box)
    emblem = create_emblem(action.status, "")
    if emblem:
        emblem_box.append(emblem)
    container = Gtk.ListBox(
        selection_mode=Gtk.SelectionMode.NONE, css_classes=["boxed-list", "sub-list"]
    )
    row.add_row(container)
    for option in action.options:
        option = cast("Option", option)
        option_row = Adw.ActionRow(title=option.label, name=option.name)
        option_row.props.activatable = True
        option_row.connect("activated", callback, option.label, option.script)
        container.append(option_row)
    return row


def create_dropdown_row(
    action: Action,
    callback: Callable[[Gtk.Widget, str, str, Callable[[], None] | None], None],
):
    """Create an ActionRow with a DropDown"""

    def on_row_selected(
        drop_down: Gtk.DropDown, g_param_spec: GObject.ParamSpec, last_status: str
    ):
        """Adapt on_row_selected event to the button style callback we received"""
        option = cast("Option", drop_down.get_selected_item())
        # don't fire activation event on initial status value resolution
        if last_status == "AWAITING_FUTURE" or last_status == option.parent.status:
            return
        callback(drop_down, option.label, option.script, option.parent.refresh)

    row = Adw.ActionRow(
        title=action.title, subtitle=action.description, focusable=False
    )

    drop_down = Gtk.DropDown(
        expression=Gtk.PropertyExpression.new(
            Option,
            expression=None,
            property_name="label",
        ),
        model=action.options,
        name=action.name,
        css_classes=["flat-dropdown"],
    )
    drop_down.connect("notify::selected-item", on_row_selected, action.status)
    align_drop_down(drop_down)

    emblem_box = Gtk.Box(width_request=16, name="emblem_box")
    row.add_suffix(emblem_box)
    row.add_suffix(drop_down)
    emblem = create_emblem(action.status, action.status_detail or "")
    action.connect("notify::status", on_status_changed, emblem_box)
    if emblem:
        emblem_box.append(emblem)
    action.bind_property(
        "selected", drop_down, "selected", GObject.BindingFlags.SYNC_CREATE
    )
    row.props.activatable_widget = drop_down
    return row


def create_button_group_row(
    action: Action,
    callback: Callable[[Gtk.Widget, str, str, Callable[[], None] | None], None],
):
    row = Adw.ActionRow(
        title=action.title,
        subtitle=action.description,
        name=action.name,
        focusable=False,
    )
    action_box = Gtk.Box(css_classes=["action-button-group"])
    emblem_box = Gtk.Box(width_request=16)
    emblem = create_emblem(action.status)
    action.connect("notify::status", on_status_changed, emblem_box, action_box)
    if emblem:
        emblem_box.append(emblem)
    row.add_suffix(emblem_box)
    row.add_suffix(action_box)
    prev = None
    for index, option in enumerate(action.options):
        option = cast("Option", option)
        label = option.name.replace("-", " ").title()
        button = Gtk.ToggleButton(
            label=label,
            name=option.name,
            css_classes=["action-button"],
            valign=Gtk.Align.CENTER,
        )
        button.connect("clicked", callback, option.label, option.script, action.refresh)
        option.bind_property(
            "active", button, "active", GObject.BindingFlags.SYNC_CREATE
        )
        option.bind_property(
            "active", button, "sensitive", GObject.BindingFlags.INVERT_BOOLEAN
        )
        if prev:
            button.set_group(prev)
        prev = button
        action_box.append(button)
        if index < len(action.options) - 1:
            action_box.append(
                Gtk.Separator(
                    orientation=Gtk.Orientation.VERTICAL,
                    css_classes=["action-button"],
                    valign=Gtk.Align.CENTER,
                )
            )
    return row


def create_row(
    action: Action,
    callback: Callable[[Gtk.Widget, str, str, Callable[[], None] | None], None],
):
    """Create row widget for an action"""

    match len(action.options):
        case val if val > 3 and action.has_status_script:
            row = create_dropdown_row(action, callback)
        case val if val > 3:
            row = create_expander_row(action, callback)
        case val if val > 0:
            row = create_button_group_row(action, callback)
        case _:
            row = Adw.ActionRow(
                title=action.title, subtitle=action.description, name=action.name
            )
            row.props.activatable = True
            row.connect("activated", callback, action.title, action.script)

    return row
