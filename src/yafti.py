import subprocess
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any, NotRequired, TypedDict

import gi
import yaml

if TYPE_CHECKING:
    from app import JankPortalWindow

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gio, GObject, Gtk  # noqa: E402

RO = GObject.PARAM_READABLE


class OptionType(TypedDict):
    id: str
    label: str
    script: str


class OptionData(GObject.Object):
    __gtype_name__ = "OptionData"

    def __init__(self, option: OptionType, **kwargs: Any):
        super().__init__(**kwargs)
        self._option = option

    @GObject.Property(type=str, default="", flags=RO)
    def id(self):
        return self._option["id"]

    @GObject.Property(type=str, default="", flags=RO)
    def label(self):
        return self._option["label"]

    @GObject.Property(type=str, default="", flags=RO)
    def script(self):
        return self._option["script"]


class ActionType(TypedDict):
    """Schema for a YAFTI action"""

    id: str
    title: str
    description: str
    script: NotRequired[str]
    default: bool
    options: NotRequired[list[OptionType]]
    status_script: NotRequired[str]


class ActionData(GObject.Object):
    """GObject adapter for ActionType"""

    __gtype_name__ = "ActionData"

    def __init__(self, action: ActionType, **kwargs: Any):
        super().__init__(**kwargs)
        self._action = action
        self._status = ""
        if "options" not in action:
            return
        self._options = Gio.ListStore(item_type=OptionData)
        for option in action["options"]:
            self._options.append(OptionData(option))

    @GObject.Property(type=str, default="", flags=RO)
    def id(self):
        return self._action["id"]

    @GObject.Property(type=str, default="", flags=RO)
    def title(self):
        return self._action["title"]

    @GObject.Property(type=str, default="", flags=RO)
    def description(self):
        return self._action["description"]

    @GObject.Property(type=str, default="", flags=RO)
    def script(self):
        return self._action.get("script", "")

    @GObject.Property(type=bool, default=False, flags=RO)
    def default(self):
        return self._action["default"]

    @property
    def options(self):
        try:
            return self._options
        except AttributeError:
            return Gio.ListStore(item_type=OptionData)

    @GObject.Property(type=str, default="", flags=RO)
    def status(self):
        """Run status_script to determine current status, cache results"""

        if "status_script" not in self._action:
            return ""
        if self._status:
            return self._status
        s = self._action["status_script"].split()

        try:
            result = subprocess.run(s, capture_output=True, text=True, check=True)
            self._status = result.stdout.strip()
            return self._status

        except FileNotFoundError:
            print(
                (
                    f"status_script for command '{self._action['id']}' not found: '{s}'"
                    f"\n(command is '{s}')"
                ),
                file=sys.stderr,
            )
            self._status = "script_failed"
            return self._status

        except subprocess.CalledProcessError as error:
            print(
                (
                    f"status_script for command '{self._action['id']}' "
                    f"returned error: {error.stderr}\n(command is '{s}')"
                ),
                file=sys.stderr,
            )
            self._status = "script_failed"
            return self._status


class PageData(GObject.Object):
    """GObject adapter for PageType"""

    __gtype_name__ = "PageData"

    def __init__(self, page: dict[str, Any], **kwargs: Any):
        super().__init__(**kwargs)
        self._page = page
        actions = Gio.ListStore(item_type=ActionData)
        for action in self._page["actions"]:
            actions.append(ActionData(action))
        self._actions = actions

    @GObject.Property(type=str, default="", flags=RO)
    def title(self):
        return self._page["title"]

    @GObject.Property(type=str, default="", flags=RO)
    def descrption(self):
        return self._page["description"]

    @GObject.Property(type=bool, default=False, flags=RO)
    def hidden(self):
        return self._page["hidden"]

    @GObject.Property(type=Gio.ListStore, default=None, flags=RO)
    def actions(self):
        return self._actions


class YaftiUI:
    def __init__(self, window: JankPortalWindow):
        """Builds ViewStackPages based on YAFTI YML, appends to window.stack widget"""

        self.window = window
        self.model = self._create_model()

        # Set up wiring for search function
        self.search_text = ""
        self.window.search_entry.connect("search-changed", self.on_search_changed)
        self.custom_filter = Gtk.CustomFilter()
        self.custom_filter.set_filter_func(self.filter)
        all_actions = Gio.ListStore(item_type=ActionData)
        filtered_model = Gtk.FilterListModel.new(all_actions, self.custom_filter)

        # Create list box with every possible action in it (for search func)
        omni_list = Gtk.ListBox(selection_mode=Gtk.SelectionMode.NONE)
        omni_list.add_css_class("boxed-list")
        omni_list.add_css_class("root-list")
        omni_list.bind_model(filtered_model, self.create_row)
        omni_scroll = Gtk.ScrolledWindow(
            vscrollbar_policy=Gtk.PolicyType.AUTOMATIC,
            propagate_natural_height=True,
            child=omni_list,
        )

        # Add everything list to ViewStack and hide
        self.search = window.stack.add_titled(
            child=omni_scroll, title="Search Results", name="search"
        )
        self.search.props.visible = False

        for screen in self.model:
            # Append actions to everything list
            all_actions.splice(
                all_actions.get_n_items(),
                0,
                [
                    screen.actions.get_item(i)
                    for i in range(screen.actions.get_n_items())
                ],
            )

            # Make box to contain header and list view
            container = Gtk.Box(
                orientation=Gtk.Orientation.VERTICAL, valign=Gtk.Align.START
            )
            description = Gtk.Label(label=screen.descrption)
            description.add_css_class("heading")
            container.append(description)

            boxed_list = Gtk.ListBox(selection_mode=Gtk.SelectionMode.NONE)
            boxed_list.add_css_class("boxed-list")
            boxed_list.add_css_class("root-list")
            boxed_list.bind_model(screen.actions, self.create_row)
            container.append(boxed_list)

            # Bash together an internal name, since none are given in the YAML
            name = screen.title.lower().replace(" ", "-").replace("!", "")
            # Wrap in a ScrolledWindow and add to ViewStack
            scrollable = Gtk.ScrolledWindow(
                vscrollbar_policy=Gtk.PolicyType.AUTOMATIC,
                propagate_natural_height=True,
                child=container,
            )
            window.stack.add_titled(child=scrollable, title=screen.title, name=name)

    def on_search_changed(self, entry: Gtk.SearchEntry):
        """Bind search entry text changes to GTK.CustomFilter changes"""

        self.window.search_bar.props.search_mode_enabled = True
        self.search_text = entry.props.text.strip().lower()
        self.custom_filter.changed(Gtk.FilterChange.DIFFERENT)
        if self.search_text:
            self.search.props.visible = True
            self.window.stack.props.visible_child_name = "search"
        else:
            self.search.props.visible = False

    def filter(self, item: ActionData):
        """Filter search results based on given text"""

        if not self.search_text:
            return True

        return (
            self.search_text in item.title.lower()
            or self.search_text in item.description.lower()
        )

    def _create_model(self, file_name: str = "/usr/share/yafti/yafti.yml"):
        """Parse YAFTI YML into Gio.ListStore"""

        try:
            path = Path(file_name)
            with path.open() as file:
                yafti: dict[str, Any] = yaml.safe_load(file) or {}
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

    def create_row(self, action: ActionData):
        """Create ActionRow widget from data in model"""
        title = action.title.replace("&", "&amp;")
        status = action.status
        title = Adw.ActionRow(title=title, subtitle=action.description)

        actions = Gtk.Box(halign=Gtk.Align.END)
        actions.add_css_class("action-button-group")

        # Create buttons for each option if action has options, or just create
        # a single button for the action's script
        if action.options:
            prev = None
            for option in action.options:
                button = Gtk.ToggleButton(
                    label=option.id.replace("-", " ").title(),
                    active=option.id == status,
                    margin_end=5,
                )
                button.connect(
                    "clicked", self.run_task, action.id, option.id, option.script
                )
                if prev:
                    button.set_group(prev)
                prev = button
                actions.append(button)
        else:
            button = Gtk.Button(label="Run")
            button.connect("clicked", self.run_task, action.id, None, action.script)
            actions.append(button)

        row = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        row.append(title)
        row.append(actions)
        return row

    def run_task(
        self, button: Gtk.Button, action: str, option: str | None, script: str
    ):
        """Pass a script along to the window's command runner"""

        print(
            f"Action {action} {f' (option {option}) ' if option else ''}"
            f"says I should run {script}"
        )
        self.window.command_runner(script)
