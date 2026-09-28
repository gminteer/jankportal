import shlex
import subprocess
from typing import TYPE_CHECKING

from gi.repository import Gio, GLib, GObject

if TYPE_CHECKING:
    from .types import OSTreeType, YaftiType

INVALID_LIST_POSITION = -1


# OSTree
class DeploymentModel(GObject.Object):
    """GObject adapter for OSTree deployment"""

    __gtype_name__ = "DeploymentModel"

    def __init__(self, index: int, deployment: OSTreeType.Deployment):
        super().__init__()
        self._data = deployment
        self._index = index
        self._overlays = [
            *deployment["packages"],
            *deployment["requested-local-packages"],
        ]

    @GObject.Property(type=int, default=-1)
    def index(self):
        return self._index

    @GObject.Property(type=str, default="")
    def image(self):
        return self._data["container-image-reference"].split("/")[-1]

    @GObject.Property(type=str, default="")
    def version(self):
        return self._data["version"]

    @GObject.Property(type=bool, default=False)
    def pinned(self):
        return self._data["pinned"]

    @GObject.Property(type=bool, default=False)
    def booted(self):
        return self._data["booted"]

    @GObject.Property(type=bool, default=False)
    def staged(self):
        return self._data["staged"]

    @property
    def overlays(self):
        return self._overlays


# YAFTI
class OptionModel(GObject.Object):
    """GObject adapter for YAFTI option"""

    __gtype_name__ = "OptionModel"

    def __init__(self, option: YaftiType.Option, parent: ActionModel):
        super().__init__()
        self._option = option
        self.parent = parent
        self.parent.connect("notify::status", lambda *_: self.notify("active"))  # type: ignore

    @GObject.Property(type=str, default="")
    def name(self):
        return self._option["id"]

    @GObject.Property(type=str, default="")
    def label(self):
        return GLib.markup_escape_text(self._option["label"])

    @GObject.Property(type=str, default="")
    def script(self):
        return self._option["script"]

    @GObject.Property(type=bool, default=False)
    def active(self):
        return self.parent.status == self.name


class ActionModel(GObject.Object):
    """GObject adapter for YAFTI action"""

    __gtype_name__ = "ActionModel"

    def __init__(self, action: YaftiType.Action):
        super().__init__()
        self._action = action
        self._status = None
        self._selected = INVALID_LIST_POSITION
        self._status_detail = None
        if "options" not in action:
            return
        self._options = Gio.ListStore(item_type=OptionModel)
        for option in action["options"]:
            self._options.append(OptionModel(option, self))

    @property
    def has_status_script(self):
        return "status_script" in self._action

    @GObject.Property(type=int, default=INVALID_LIST_POSITION)
    def selected(self):
        return self._selected

    @GObject.Property(type=str, default="")
    def status_detail(self):
        return self._status_detail

    @GObject.Property(type=str, default="")
    def name(self):
        return self._action["id"]

    @GObject.Property(type=str, default="")
    def title(self):
        return GLib.markup_escape_text(self._action["title"])

    @GObject.Property(type=str, default="")
    def description(self):
        return GLib.markup_escape_text(self._action["description"])

    @GObject.Property(type=str, default="")
    def script(self):
        return self._action.get("script", "")

    @GObject.Property(type=bool, default=False)
    def default(self):
        return self._action["default"]

    @GObject.Property(
        type=Gio.ListStore[OptionModel], default=Gio.ListStore(item_type=OptionModel)
    )
    def options(self):
        try:
            return self._options
        except AttributeError:
            return Gio.ListStore(item_type=OptionModel)

    @GObject.Property(type=str, default="")
    def status(self):
        """Run status_script to determine current status, cache results"""

        if "status_script" not in self._action:
            return "NO_STATUS"
        if self._status:
            return self._status
        s = []
        try:
            # Kludge for protonplus status script
            # (the rest of the "scripts" work fine without bash loaded)
            if self._action["status_script"].startswith("if "):
                s = [
                    "bash",
                    "--noprofile",
                    "--norc",
                    "-lc",
                    self._action["status_script"],
                ]
            else:
                s = shlex.split(self._action["status_script"])

            result = subprocess.run(
                s,
                capture_output=True,
                text=True,
                check=True,
            )
            self._status = result.stdout.strip()
            self._status_detail = None
            for index, option in enumerate(self._options):
                if option.name == self._status:
                    self._selected = index
                    self.notify("selected")
                    break

        except FileNotFoundError:
            # Kludge for steamosctl only being in deck images
            if s[0] == "steamosctl":
                self._status = "NOT_A_DECK"
                self._status_detail = None
            else:
                self._status = "NOT_FOUND"
                self._status_detail = s[0]

        except subprocess.CalledProcessError as error:
            self._status = "ERROR"
            self._status_detail = error.stderr

        self.notify("status")
        return self._status


class PageModel(GObject.Object):
    """GObject adapter for YAFTI page"""

    __gtype_name__ = "PageModel"

    def __init__(self, page: YaftiType.Page):
        super().__init__()
        self._page = page
        actions = Gio.ListStore(item_type=ActionModel)
        for action in self._page["actions"]:
            actions.append(ActionModel(action))
        self._actions = actions

    @GObject.Property(type=str, default="")
    def title(self):
        return self._page["title"]

    @GObject.Property(type=str, default="")
    def descrption(self):
        return self._page["description"]

    @GObject.Property(type=bool, default=False)
    def hidden(self):
        return self._page["hidden"]

    @GObject.Property(type=Gio.ListStore, default=None)
    def actions(self):
        return self._actions
