"""Adapt rpm-ostree / skopeo data to GObjects"""

import asyncio
import json
from typing import TYPE_CHECKING

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gio, GObject, Gtk  # noqa:E402

if TYPE_CHECKING:
    from collections.abc import Callable

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


async def create_deployment_model(
    panic: Callable[[str], None],
) -> tuple[Gio.ListStore[Deployment], str, str]:
    """Parse rpm-ostree status into Gio.ListStore"""
    try:
        model = Gio.ListStore(item_type=Deployment)
        process = await asyncio.create_subprocess_exec(
            "rpm-ostree",
            "status",
            "--json",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await process.communicate()

        if process.returncode != 0:
            panic(f"rpm-ostree error: {stderr}")
        ostree_status = json.loads(stdout)

        image: str = ""
        tag: str = ""
        for index, deployment in enumerate(ostree_status["deployments"]):
            model.append(Deployment(index=index, deployment=deployment))
            if deployment["booted"]:
                image, tag = (
                    deployment["container-image-reference"].split("/")[-1].split(":")
                )
        return model, image, tag

    except FileNotFoundError:
        panic("rpm-ostree not in $PATH")
        raise RuntimeError()


async def create_tag_model(image: str, panic: Callable[[str], None]) -> Gtk.StringList:
    """Get tags for a given image from skopeo"""

    try:
        process = await asyncio.create_subprocess_exec(
            "skopeo",
            "list-tags",
            f"docker://ghcr.io/ublue-os/{image}",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await process.communicate()
        if process.returncode != 0:
            panic(f"skopeo error: {stderr}")

        raw_tags = json.loads(stdout)["Tags"]
        # filter for just stable and testing tags
        tags = [tag for tag in raw_tags if tag.startswith(("stable", "testing"))]
        return Gtk.StringList.new(sorted(tags))

    except FileNotFoundError:
        panic("skopeo not in $PATH")
        raise RuntimeError()
