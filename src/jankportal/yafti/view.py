import sys
from pathlib import Path
from typing import TYPE_CHECKING, cast

import gi
import yaml

from jankportal.lib import align_drop_down

from . import templates
from .models import Action, Option, Page

if TYPE_CHECKING:
    from collections.abc import Callable

    from jankportal.app import JankWindow

    from .types import Root, TitledPage


gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gio, GObject, Gtk  # noqa: E402


def create_model(
    panic_func: Callable[[str], None], file_name: str = "/usr/share/yafti/yafti.yml"
):
    """Parse YAFTI YML into Gio.ListStore"""
    try:
        path = Path(file_name)
        with path.open() as file:
            yafti = cast("Root", yaml.safe_load(file))
            if not yafti:
                panic_func("Error parsing yafti")
                sys.exit(1)

            model = Gio.ListStore(item_type=Page)
            for screen in yafti["screens"]:
                model.append(Page(screen))

            return model

    except FileNotFoundError:
        panic_func(f"yafti scripts file not found at {file_name}")
        sys.exit(1)


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
        if last_status == "AWAITING_FUTURE":
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
    drop_down.connect("notify::selected-item", on_row_selected, action.status)
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


def create_pages(
    model: Gio.ListStore[Page],
    callback: Callable[[Gtk.Widget, str, str, Callable[[], None] | None], None],
    filter: Gtk.CustomFilter,
):
    def row_factory(action: Action):
        return create_row(action, callback)

    # Everything list for search func
    all_actions = Gio.ListStore(item_type=Action)
    filtered_model = Gtk.FilterListModel.new(all_actions, filter)
    search_page = templates.Page()
    search_page.description.props.label = "Search Results"
    search_page.action_list.bind_model(filtered_model, row_factory)
    pages: list[TitledPage] = [
        {
            "title": "Search Results",
            "name": "search",
            "visible": False,
            "page": search_page,
        }
    ]

    for screen in model:
        # Append actions to everything list
        all_actions.splice(
            all_actions.get_n_items(),
            0,
            [screen.actions.get_item(i) for i in range(screen.actions.get_n_items())],
        )
        page = templates.Page()
        page.description.props.label = screen.descrption
        page.action_list.bind_model(screen.actions, row_factory)

        # Bash together an internal name, since none are given in the YAML
        name = screen.title.lower().replace(" ", "-").replace("!", "")
        pages.append(
            {"name": name, "title": screen.title, "visible": True, "page": page}
        )

    return pages


def filter(item: Action, search_text: str):
    """Filter search results based on given text"""

    if not search_text:
        return True

    return search_text in item.title.lower() or search_text in item.description.lower()


class YaftiView:
    def __init__(self, window: JankWindow):
        """Builds ViewStackPages based on YAFTI YML, appends to window.stack widget"""

        self.window = window
        model = create_model(window.panic)

        # Set up wiring for search function
        self.search_text = ""
        self.last_page = "welcome"
        self.window.search.connect("search-changed", self.on_search_changed)
        self.window.search.connect("search-started", self.on_search_started)
        self.window.search.connect("stop-search", self.on_stop_search)

        def filter_func(item: Action):
            return filter(item, self.search_text)

        self._filter = Gtk.CustomFilter.new(filter_func)

        pages = create_pages(model, self.on_widget_activated, self._filter)
        for page in pages:
            bound_page = window.stack.add_titled(
                child=page["page"], title=page["title"], name=page["name"]
            )
            bound_page.props.visible = page["visible"]

        search_wrapper = cast("Gtk.Widget", window.stack.get_child_by_name("search"))
        self.search = window.stack.get_page(search_wrapper)

    def on_widget_activated(
        self,
        widget: Gtk.Widget,
        title: str,
        script: str,
        vte_done_callback: Callable[[], None] | None = None,
    ):
        """Pass a script along to the window's command runner"""

        self.window.command_runner(title, script, vte_done_callback=vte_done_callback)

    def on_search_changed(self, entry: Gtk.SearchEntry):
        """Bind search entry text changes to GTK.CustomFilter changes"""

        self.search_text = entry.props.text.strip().lower()
        self._filter.changed(Gtk.FilterChange.DIFFERENT)
        if self.search_text:
            if self.window.stack.props.visible_child_name != "search":
                self.last_page = self.window.stack.props.visible_child_name
            self.window.stack.props.visible_child_name = "search"
            self.window.split_view.props.show_sidebar = False
        else:
            self.window.stack.props.visible_child_name = self.last_page
            self.window.split_view.props.show_sidebar = True

    def on_search_started(self, entry: Gtk.SearchEntry):
        self.window.search.grab_focus()

    def on_stop_search(self, entry: Gtk.SearchEntry):
        self.window.search.props.text = ""
