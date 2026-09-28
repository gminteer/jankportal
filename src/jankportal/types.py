from typing import TYPE_CHECKING, NotRequired, TypedDict

if TYPE_CHECKING:
    import gi

    gi.require_version("Gtk", "4.0")
    from gi.repository import Gtk


class OSTreeType:
    """Namespace for OSTree related types"""

    Deployment = TypedDict(
        "Deployment",
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
    """Partial schema for rpm-ostree status --json"""


class YaftiType:
    """Namespace for YAFTI related types"""

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
        options: NotRequired[list[YaftiType.Option]]
        status_script: NotRequired[str]

    class Page(TypedDict):
        """Schema for a YAFTI page"""

        title: str
        description: str
        hidden: bool
        actions: list[YaftiType.Action]

    class Root(TypedDict):
        """Schema for the root of a YAFTI YAML file"""

        title: str
        screens: list[YaftiType.Page]

    class TitledPage(TypedDict):
        name: str
        title: str
        visible: bool
        page: Gtk.ScrolledWindow
