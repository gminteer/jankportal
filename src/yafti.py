import gi
import subprocess
import sys
import yaml

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gio, GObject, Gtk, Adw

# from app import vte

RO = GObject.PARAM_READABLE


class OptionData(GObject.Object):
    __gtype_name__ = "OptionData"

    def __init__(self, option, **kwargs):
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


class ActionData(GObject.Object):
    __gtype_name__ = "ActionData"

    def __init__(self, action, **kwargs):
        super().__init__(**kwargs)
        self._action = action
        if self._action.get("options", ""):
            self._options = Gio.ListStore(item_type=OptionData)
            for option in self._action["options"]:
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
        return self._action["script"]

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
        s = self._action.get("status_script", "").split()
        if not s:
            return ""

        try:
            result = subprocess.run(s, capture_output=True, text=True, check=True)
            return result.stdout.strip()

        except FileNotFoundError:
            print(
                f"status_script for command '{self._action["id"]}' not found: '{s}'\n(command is '{s}')",
                file=sys.stderr,
            )
            return "unknown"

        except subprocess.CalledProcessError as error:
            print(
                f"status_script for command '{self._action["id"]}' returned error: {error.stderr}\n(command is '{s}')"
            )
            return "unknown"


class PageData(GObject.Object):
    __gtype_name__ = "PageData"

    def __init__(self, page, **kwargs):
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


class YaftiUI(object):
    def __init__(self, window):
        self.window = window
        self.model = self._create_model()
        for screen in self.model:
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

            name = screen.title.lower().replace(" ", "-").replace("!", "")
            scrollable = Gtk.ScrolledWindow(
                vscrollbar_policy=Gtk.PolicyType.AUTOMATIC,
                propagate_natural_height=True,
                child=container,
            )
            window.stack.add_titled(child=scrollable, title=screen.title, name=name)

    def _create_model(self, file_name="/usr/share/yafti/yafti.yml"):
        try:
            with open(file_name, "r") as file:
                yafti = yaml.safe_load(file) or {}
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

    def create_row(self, action):
        title = action.title.replace("&", "&amp;")
        status = action.status
        title = Adw.ActionRow(title=title, subtitle=action.description)

        actions = Gtk.Box(halign=Gtk.Align.END)
        actions.add_css_class("action-button-group")

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

    def run_task(self, button, action, option, script):
        print(
            f"Action {action} {f" (option {option}) " if option else ""}says I should run {script}"
        )
        self.window.command_runner(script)
