#!/usr/bin/env bash
eval "$(python3 jank_env.py)"

PKG_VERSION=$(distrobox enter jankbuild -- uvx hatch version)

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
