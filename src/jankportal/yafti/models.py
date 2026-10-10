"""Adapt YAFTI data to GObjects"""

import asyncio
import shlex
from pathlib import Path
from typing import TYPE_CHECKING, cast

import yaml
from gi.repository import Gio, GLib, GObject

if TYPE_CHECKING:
    from collections.abc import Callable

    from . import types


INVALID_LIST_POSITION = -1


class Option(GObject.Object):
    """GObject adapter for YAFTI option"""

    __gtype_name__ = "OptionModel"

    def __init__(self, option: types.Option, parent: Action):
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


class Action(GObject.Object):
    """GObject adapter for YAFTI action"""

    __gtype_name__ = "ActionModel"

    def __init__(self, action: types.Action):
        super().__init__()
        self._action = action
        self._status = None
        self._selected = INVALID_LIST_POSITION
        self._status_detail = None
        self._options = Gio.ListStore(item_type=Option)
        if "options" not in action:
            return
        for option in action["options"]:
            self._options.append(Option(option, self))
        if "status_script" in action:
            self.refresh()

    def _cleanup_task(self, task: asyncio.Task[None]):
        self._async_task = None

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
        type=Gio.ListStore[Option], default=Gio.ListStore(item_type=Option)
    )
    def options(self):
        return self._options

    def refresh(self):
        if "status_script" not in self._action:
            return
        self._async_task = asyncio.create_task(
            self._get_status(self._action["status_script"])
        )
        self._async_task.add_done_callback(self._cleanup_task)
        self._status = "AWAITING_FUTURE"

    async def _get_status(self, status_script: str):
        # Kludge for protonplus status script
        # (the rest of the "scripts" work fine without bash loaded)
        if status_script.startswith("if "):
            s = [
                "bash",
                "--noprofile",
                "--norc",
                "-lc",
                status_script,
            ]
        else:
            s = shlex.split(status_script)
        try:
            process = await asyncio.create_subprocess_exec(
                *s, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await process.communicate()
            if process.returncode != 0:
                self._status = "ERROR"
                self._status_detail = stderr.decode()
                self._selected = INVALID_LIST_POSITION
                return

            self._status = stdout.decode().strip()
            self._status_detail = None
            for index, option in enumerate(self._options):
                if option.name == self._status:
                    self._selected = index
                    break

        except FileNotFoundError:
            # Kludge for steamosctl only being in deck images
            if s[0] == "steamosctl":
                self._status = "NOT_A_DECK"
                self._status_detail = None
            else:
                self._status = "NOT_FOUND"
                self._status_detail = s[0]
            self._selected = INVALID_LIST_POSITION

        finally:
            self.notify("selected")
            self.notify("status")

    @GObject.Property(type=str, default="")
    def status(self):
        """Run status_script to determine current status, cache results"""

        if "status_script" not in self._action:
            return "NO_STATUS"
        return self._status


class Page(GObject.Object):
    """GObject adapter for YAFTI page"""

    __gtype_name__ = "PageModel"

    def __init__(self, page: types.Page):
        super().__init__()
        self._page = page
        actions = Gio.ListStore(item_type=Action)
        for action in self._page["actions"]:
            actions.append(Action(action))
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


def create_model(
    panic: Callable[[str], None], file_name: str = "/usr/share/yafti/yafti.yml"
) -> Gio.ListStore[Page]:
    """Parse YAFTI YML into Gio.ListStore"""
    try:
        with Path(file_name).open() as file:
            yafti = cast("types.Root", yaml.safe_load(file))
            if not yafti:
                panic("Error parsing yafti")
                raise RuntimeError()

            model = Gio.ListStore(item_type=Page)
            for screen in yafti["screens"]:
                model.append(Page(screen))

            return model

    except FileNotFoundError:
        panic(f"yafti scripts file not found at {file_name}")
        raise RuntimeError()
