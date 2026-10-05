#!/usr/bin/env bash
PKG_NAME=$(python3 -c "import tomllib; print(tomllib.load(open('pyproject.toml', 'rb'))['project']['name'])")
PKG_VERSION=$(uvx hatch version)
PKG_SUMMARY=$(python3 -c "import tomllib; print(tomllib.load(open('pyproject.toml', 'rb'))['project']['description'])")
PKG_DESCRIPTION=$(python3 -c "import tomllib; print(tomllib.load(open('pyproject.toml', 'rb'))['tool']['rpm']['description'])")
PKG_LICENSE=$(python3 -c "import tomllib; print(tomllib.load(open('pyproject.toml', 'rb'))['project']['license'])")
PKG_URL=$(python3 -c "import tomllib; print(tomllib.load(open('pyproject.toml', 'rb'))['project']['urls']['Homepage'])")
PKG_REQUIRES=$(python3 -c "import tomllib; print(' '.join([dep.split('/')[-1].replace('@>=',' >= ') for dep in tomllib.load(open('pyproject.toml', 'rb'))['external']['host-requires']]))")
PKG_BUILD_REQUIRES=$(python3 -c "import tomllib; print(' '.join([dep.split('/')[-1].replace('@>=',' >= ') for dep in tomllib.load(open('pyproject.toml', 'rb'))['external']['build-requires']]))")

distrobox enter jankbuild -- uv build
distrobox enter jankbuild -- rpmbuild\
    --define "pkg_name $PKG_NAME"\
    --define "pkg_version $PKG_VERSION"\
    --define "pkg_summary $PKG_SUMMARY"\
    --define "pkg_description $PKG_DESCRIPTION"\
    --define "pkg_license $PKG_LICENSE"\
    --define "pkg_url $PKG_URL"\
    --define "pkg_requires $PKG_REQUIRES"\
    --define "pkg_build_requires $PKG_BUILD_REQUIRES"\
    --define "_sourcedir $(pwd)/dist"\
    --define "_rpmdir $(pwd)/dist"\
    --define "_specdir $(pwd)"\
    --define "_srcrpmdir $(pwd)/dist"\
    -ba $PKG_NAME.spec

echo If you didn\'t see any errors, the RPM should be built.
echo To install, type \"rpm-ostree install dist/noarch/$PKG_NAME-$PKG_VERSION-1.fc44.noarch.rpm\" \(and reboot\)
