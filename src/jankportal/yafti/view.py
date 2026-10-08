from typing import TYPE_CHECKING, cast

import gi

from . import templates
from .models import Action, Page, create_model
from .rows import create_row

if TYPE_CHECKING:
    from collections.abc import Callable

    from jankportal.app import JankWindow

    from .types import TitledPage


gi.require_version("Gtk", "4.0")
from gi.repository import Gio, Gtk  # noqa: E402


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
