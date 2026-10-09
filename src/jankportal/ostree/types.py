"""Type hint for json dictionary"""

from typing import TypedDict

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
