#!/usr/bin/env bash
eval "$(python3 jank_env.py)"

distrobox-create -n jankbuild -i quay.io/fedora/fedora-toolbox
distrobox-enter jankbuild -- sudo dnf install -y\
    python3-devel\
    rpmdevtools\
    $BOX_PYTHON_DEPS\
    $BOX_PYTHON_BUILD_DEPS\
    $BOX_DEPS\
    $BOX_BUILD_DEPS

echo If you didn\'t see any errors, ./jank_build.sh should work.
