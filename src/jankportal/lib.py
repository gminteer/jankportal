import shlex
import subprocess
from typing import NotRequired, TypedDict

from gi.repository import Gio, GLib, GObject, Gtk

# Resources
RES_PATH = "/io/github/gminteer/jankportal"


class JankWarning(UserWarning):
    """Raised on non-fatal errors"""

    def __init__(self, title: str, message: str):
        super().__init__(self)
        self.title = title
        self.message = message


def end_align_drop_down_popover(drop_down: Gtk.DropDown) -> None:
    """Set a DropDown's child PopOver to align with the end of the box"""
    child = drop_down.get_first_child()
    while child is not None:
        if isinstance(child, Gtk.Popover):
            child.props.halign = Gtk.Align.END
            break

        child = child.get_next_sibling()


# OSTree types
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

    def __init__(self, index: int, deployment: DeploymentType):
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
    def image_ref(self):
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


# YAFTI types
class OptionType(TypedDict):
    """Schema for a YAFTI action's option"""

    id: str
    label: str
    script: str


class OptionData(GObject.Object):
    """GObject adapter for OptionType"""

    __gtype_name__ = "OptionData"

    def __init__(self, option: OptionType):
        super().__init__()
        self._option = option

    @GObject.Property(type=str, default="")
    def id(self):
        return self._option["id"]

    @GObject.Property(type=str, default="")
    def label(self):
        return GLib.markup_escape_text(self._option["label"])

    @GObject.Property(type=str, default="")
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

    def __init__(self, action: ActionType):
        super().__init__()
        self._action = action
        self._status = ""
        if "options" not in action:
            return
        self._options = Gio.ListStore(item_type=OptionData)
        for option in action["options"]:
            self._options.append(OptionData(option))

    @property
    def has_status_script(self):
        return "status_script" in self._action

    @GObject.Property(type=str, default="")
    def id(self):
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
        type=Gio.ListStore[OptionData], default=Gio.ListStore(item_type=OptionData)
    )
    def options(self):
        try:
            return self._options
        except AttributeError:
            return Gio.ListStore(item_type=OptionData)

    @GObject.Property(type=str, default="")
    def status(self):
        """Run status_script to determine current status, cache results"""

        if "status_script" not in self._action:
            return ""
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
            return self._status
        except FileNotFoundError:
            # Kludge for steamosctl only being in deck images
            if s[0] == "steamosctl":
                self._status = "NOT_A_DECK"
                return self._status
            self._status = "NOT_FOUND"
            raise JankWarning(
                title=f"'{self._action['title']}' error",
                message=f"Status command '{s[0]}' not found",
            )
        except subprocess.CalledProcessError as error:
            self._status = "ERROR"
            raise JankWarning(
                title=f"'{self._action['title']}' error",
                message=f"Status result: '{error.stderr}'",
            )


class PageType(TypedDict):
    """Schema for a YAFTI page"""

    title: str
    description: str
    hidden: bool
    actions: list[ActionType]


class PageData(GObject.Object):
    """GObject adapter for PageType"""

    __gtype_name__ = "PageData"

    def __init__(self, page: PageType):
        super().__init__()
        self._page = page
        actions = Gio.ListStore(item_type=ActionData)
        for action in self._page["actions"]:
            actions.append(ActionData(action))
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


class YaftiType(TypedDict):
    """Schema for YAFTI dictionary"""

    title: str
    screens: list[PageType]
