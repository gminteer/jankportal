from typing import TYPE_CHECKING

from gi.repository import GObject

if TYPE_CHECKING:
    from . import types


class Deployment(GObject.Object):
    """GObject adapter for OSTree deployment"""

    __gtype_name__ = "DeploymentModel"

    def __init__(self, index: int, deployment: types.Deployment):
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
