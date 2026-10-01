#!/usr/bin/env bash

distrobox-create -n jankbuild -i quay.io/fedora/fedora-toolbox
distrobox-enter jankbuild -- sudo dnf install\
blueprint-compiler\
glib2-devel\
python3-devel\
python3-hatchling\
python3-uv-dynamic-versioning\
python3-markdown\
python3-pyyaml\
libadwaita\
vte-291-gtk4\
webkitgtk6.0\
rpmdevtools\

echo If you didn\'t see any errors, ./jankbuild.sh should work
