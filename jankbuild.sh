#!/usr/bin/env bash
PKG_VERSION=$(uvx hatch version)
PKG_SUMMARY=$(python3 -c "import tomllib; print(tomllib.load(open('pyproject.toml', 'rb'))['project']['description'])")
PKG_REQUIRES=$(python3 -c "import tomllib; print(' '.join([dep.split('/')[-1].replace('@>=',' >= ') for dep in tomllib.load(open('pyproject.toml', 'rb'))['external']['host-requires']]))")
PKG_BUILD_REQUIRES=$(python3 -c "import tomllib; print(' '.join([dep.split('/')[-1].replace('@>=',' >= ') for dep in tomllib.load(open('pyproject.toml', 'rb'))['external']['build-requires']]))")

distrobox enter jankbuild -- uv build
distrobox enter jankbuild -- rpmbuild\
    --define "pkg_version $PKG_VERSION"\
    --define "pkg_summary $PKG_SUMMARY"\
    --define "pkg_requires $PKG_REQUIRES"\
    --define "pkg_build_requires $PKG_BUILD_REQUIRES"\
    --define "_sourcedir $(pwd)/dist"\
    --define "_rpmdir $(pwd)/dist"\
    --define "_specdir $(pwd)"\
    --define "_srcrpmdir $(pwd)/dist"\
    -ba jankportal.spec

echo If you didn\'t see any errors, the RPM should be built.
echo To install, type \"rpm-ostree install dist/noarch/jankportal-$PKG_VERSION\-1.fc44.noarch.rpm" \(and reboot\)
