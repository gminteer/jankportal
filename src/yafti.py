import sys
from pathlib import Path
from typing import TYPE_CHECKING, TypedDict, cast

import gi
import yaml

from datatypes import ActionData, PageData

if TYPE_CHECKING:
    from collections.abc import Callable

    from app import JankPortalWindow
    from datatypes import YaftiType


gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gio, Gtk  # noqa: E402


class TitledPage(TypedDict):
    name: str
    title: str
    visible: bool
    page: Gtk.ScrolledWindow


def create_model(file_name: str = "/usr/share/yafti/yafti.yml"):
    """Parse YAFTI YML into Gio.ListStore"""

    try:
        path = Path(file_name)
        with path.open() as file:
            yafti = cast("YaftiType", yaml.safe_load(file))
            if not yafti:
                print("Error parsing yafti", file=sys.stderr)
                sys.exit(1)

            model = Gio.ListStore(item_type=PageData)
            for screen in yafti["screens"]:
                model.append(PageData(screen))

            return model

    except FileNotFoundError:
        print(f"yafti scripts file not found at {file_name}", file=sys.stderr)
        sys.exit(1)


def create_row(
    action: ActionData, on_button_clicked: Callable[[Gtk.Button, str, str], None]
):
    """Create ActionRow widget from data in model"""

    title = Adw.ActionRow(
        title=action.title, subtitle=action.description, valign=Gtk.Align.START
    )

    actions = Gtk.Box(halign=Gtk.Align.END, css_classes=["action-button-group"])

    # Create buttons for each option if action has options, or just create
    # a single button for the action's script
    if action.options:
        prev = None
        for index, option in enumerate(action.options):
            button = Gtk.ToggleButton(
                label=option.id.replace("-", " ").title(),
                active=option.id == action.status,
                css_classes=["action-button"],
            )
            button.connect("clicked", on_button_clicked, option.label, option.script)
            if prev:
                button.set_group(prev)
            prev = button
            actions.append(button)
            if index < action.options.get_n_items() - 1:
                actions.append(
                    Gtk.Separator(
                        orientation=Gtk.Orientation.VERTICAL,
                        css_classes=["action-button"],
                    )
                )
    else:
        button = Gtk.Button(label="Run", css_classes=["action-button"])
        button.connect("clicked", on_button_clicked, action.title, action.script)
        actions.append(button)

    row = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
    row.append(title)
    row.append(actions)
    return row


def create_pages(
    model: Gio.ListStore[PageData],
    on_button_clicked: Callable[[Gtk.Button, str, str], None],
    filter: Gtk.CustomFilter,
):
    def row_factory(action: ActionData):
        return create_row(action, on_button_clicked)

    # Everything list for search func
    all_actions = Gio.ListStore(item_type=ActionData)
    filtered_model = Gtk.FilterListModel.new(all_actions, filter)
    omni_list = Gtk.ListBox(
        selection_mode=Gtk.SelectionMode.NONE,
        valign=Gtk.Align.START,
        css_classes=["boxed-list", "root-list"],
    )
    omni_list.bind_model(filtered_model, row_factory)
    omni_scroll = Gtk.ScrolledWindow(
        vscrollbar_policy=Gtk.PolicyType.AUTOMATIC,
        propagate_natural_height=True,
        child=omni_list,
    )
    pages: list[TitledPage] = [
        {
            "title": "Search Results",
            "name": "search",
            "visible": False,
            "page": omni_scroll,
        }
    ]

    for screen in model:
        # Append actions to everything list
        all_actions.splice(
            all_actions.get_n_items(),
            0,
            [screen.actions.get_item(i) for i in range(screen.actions.get_n_items())],
        )

        # Make box to contain header and list view
        container = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL, valign=Gtk.Align.START
        )
        container.append(Gtk.Label(label=screen.descrption, css_classes=["heading"]))

        action_list = Gtk.ListBox(
            selection_mode=Gtk.SelectionMode.NONE,
            css_classes=["boxed-list", "root-list"],
        )
        action_list.bind_model(screen.actions, row_factory)
        container.append(action_list)

        # Bash together an internal name, since none are given in the YAML
        name = screen.title.lower().replace(" ", "-").replace("!", "")
        # Wrap in a ScrolledWindow and add to ViewStack
        scrollable = Gtk.ScrolledWindow(
            vscrollbar_policy=Gtk.PolicyType.AUTOMATIC,
            propagate_natural_height=True,
            child=container,
        )
        pages.append(
            {"name": name, "title": screen.title, "visible": True, "page": scrollable}
        )

    return pages


def filter(item: ActionData, search_text: str):
    """Filter search results based on given text"""

    if not search_text:
        return True

    return search_text in item.title.lower() or search_text in item.description.lower()


class YaftiUI:
    def __init__(self, window: JankPortalWindow):
        """Builds ViewStackPages based on YAFTI YML, appends to window.stack widget"""

        self.window = window
        model = create_model()

        # Set up wiring for search function
        self.search_text = ""
        self.last_page = "welcome"
        self.window.search_entry.connect("search-changed", self.on_search_changed)

        def filter_func(item: ActionData):
            return filter(item, self.search_text)

        self._filter = Gtk.CustomFilter.new(filter_func)

        pages = create_pages(model, self.on_button_clicked, self._filter)
        for page in pages:
            bound_page = window.stack.add_titled(
                child=page["page"], title=page["title"], name=page["name"]
            )
            bound_page.props.visible = page["visible"]

        search_wrapper = window.stack.get_child_by_name("search")
        if not isinstance(search_wrapper, Gtk.Widget):
            # This shouldn't be possible
            print("missing search page!", sys.stderr)
            sys.exit(1)
        self.search = window.stack.get_page(search_wrapper)

    def on_button_clicked(self, button: Gtk.Button, title: str, script: str):
        """Pass a script along to the window's command runner"""

        self.window.command_runner(title, script)

    def on_search_changed(self, entry: Gtk.SearchEntry):
        """Bind search entry text changes to GTK.CustomFilter changes"""

        self.window.search_bar.props.search_mode_enabled = True
        self.search_text = entry.props.text.strip().lower()
        self._filter.changed(Gtk.FilterChange.DIFFERENT)
        if self.search_text:
            self.search.props.visible = True
            if self.window.stack.props.visible_child_name != "search":
                self.last_page = self.window.stack.props.visible_child_name
            self.window.stack.props.visible_child_name = "search"
        else:
            self.search.props.visible = False
            self.window.stack.props.visible_child_name = self.last_page
