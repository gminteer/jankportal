from typing import TYPE_CHECKING, NotRequired, TypedDict

if TYPE_CHECKING:
    from . import templates


class Option(TypedDict):
    """Schema for a YAFTI action's options"""

    id: str
    label: str
    script: str


class Action(TypedDict):
    """Schema for a YAFTI action"""

    id: str
    title: str
    description: str
    script: NotRequired[str]
    default: bool
    options: NotRequired[list[Option]]
    status_script: NotRequired[str]


class Page(TypedDict):
    """Schema for a YAFTI page"""

    title: str
    description: str
    hidden: bool
    actions: list[Action]


class Root(TypedDict):
    """Schema for the root of a YAFTI YAML file"""

    title: str
    screens: list[Page]


class TitledPage(TypedDict):
    name: str
    title: str
    visible: bool
    page: templates.Page
