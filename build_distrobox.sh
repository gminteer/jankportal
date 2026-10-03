#!/usr/bin/env bash

EXTERNAL_DEPS=$(python3 -c "import tomllib; print(' '.join([dep.split('/')[-1].split('@')[0] for dep in tomllib.load(open('pyproject.toml', 'rb'))['external']['host-requires']]))")
EXTERNAL_BUILD_DEPS=$(python3 -c "import tomllib; print(' '.join([dep.split('/')[-1].split('@')[0] for dep in tomllib.load(open('pyproject.toml', 'rb'))['external']['build-requires']]))")
PYTHON_DEPS=$(python3 -c "import tomllib; print(' '.join([f\"python3-{dep.split('>')[0]}\" for dep in tomllib.load(open('pyproject.toml', 'rb'))['project']['dependencies']]))")
#bodge around pyobject-stubs
PYTHON_BUILD_DEPS=$(python3 -c "import tomllib; print(' '.join([f\"python3-{dep.split('>')[0]}\" for dep in tomllib.load(open('pyproject.toml', 'rb'))['dependency-groups']['dev'] if \"pygobject-stubs\" not in dep]))")

distrobox-create -n jankbuild -i quay.io/fedora/fedora-toolbox
distrobox-enter jankbuild -- sudo dnf install -y\
    python3-devel\
    rpmdevtools\
    $PYTHON_DEPS\
    $PYTHON_BUILD_DEPS\
    $EXTERNAL_DEPS\
    $EXTERNAL_BUILD_DEPS

echo If you didn\'t see any errors, ./jankbuild.sh should work
