"""Reflect project metadata into envrionment variables"""

import tomllib
from pathlib import Path


def dnf_deps(deps: list[str]) -> str:
    """Translate PEP 725 external deps into a space separated list
    for dnf by blindly assuming the string format is
    `stuff/to/ignore/$packagename@>=$min_version`"""

    parsed = (dep.split("/")[-1].split("@>=")[0] for dep in deps)
    return " ".join(parsed)


def py_deps(deps: list[str]) -> str:
    """Translate pyproject dependencies into a space separated list for
    dnf by hacking off the version and prepending 'python3-'. Also ignore
    any package names with '-stubs' in the name on the assumption they're
    type hinting packages that only exist in PyPI"""

    parsed = (f"python3-{dep.split('>=')[0]}" for dep in deps if "-stubs" not in dep)
    return " ".join(parsed)


def spec_deps(deps: list[str]) -> str:
    """Translate PEP 725 external deps into a space sepeated list
    for an RPM spec file by blindly assuming the string format is
    `stuff/to/ignore/$packagename@>=$min_version`"""

    parsed = (dep.split("/")[-1].replace("@>=", " >= ") for dep in deps)
    return " ".join(parsed)


with Path("pyproject.toml").open("rb") as file:
    cfg = tomllib.load(file)
    print(f"export EXTERNAL_DEPS='{dnf_deps(cfg['external']['host-requires'])}'")
    print(f"export EXTERNAL_BUILD_DEPS='{dnf_deps(cfg['external']['build-requires'])}'")
    print(f"export PYTHON_DEPS='{py_deps(cfg['project']['dependencies'])}'")
    print(f"export PYTHON_BUILD_DEPS='{py_deps(cfg['dependency-groups']['dev'])}'")
    print(f"export PKG_NAME='{cfg['project']['name']}'")
    print(f"export PKG_SUMMARY='{cfg['project']['description']}'")
    print(f"export PKG_DESCRIPTION='{cfg['tool']['rpm']['description']}'")
    print(f"export PKG_LICENSE='{cfg['project']['license']}'")
    print(f"export PKG_URL='{cfg['project']['urls']['Homepage']}'")
    print(f"export PKG_REQUIRES='{spec_deps(cfg['external']['host-requires'])}'")
    print(f"export PKG_BUILD_REQUIRES='{spec_deps(cfg['external']['build-requires'])}'")
