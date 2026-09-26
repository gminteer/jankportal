# Jank Portal

A Clone of [Bazzite Portal](https://github.com/xXJSONDeruloXx/yafti-gtk), also using Python and GTK, but not directly based off of it. The project started mostly as an excuse to get back into Python, and learn a GUI toolkit that isn't Tkinter along the way. It's mostly functional, and incorporates a partially implemented wrapper around `rpm-ostree` and `bazzite-rollback-helper` in the deployments tab, but it's definitely not ready for prime time yet.

## Installation

To be figured out.

### External Dependencies

#### Runtime

99% of Jank Portal's runtime dependencies should be present out of the box on Bazzite (I'm not sure how applicable this tool is to any other distro to be honest):

- [PyGObject](https://pygobject.gnome.org/)
- [ostree](https://ostreedev.github.io/ostree/man/ostree.html), [rpm-ostree](https://coreos.github.io/rpm-ostree/), and [skopeo](https://github.com/podman-container-tools/skopeo) commands in $PATH
- A [yafti.yml](file:///usr/share/yafti/yafti.yml) file in `/usr/share/yafti`

The only runtime dependency that'll need to be manually installed (and I suspect it's there on -gnome images) is the [GNOME VTE library](https://gitlab.gnome.org/GNOME/vte). I've just got it layered with `rpm-ostree`, but I know that's bad manners in Bazzite-land and I suspect there's a better way to do it, but haven't looked into that too far yet.

#### Build

- [blueprint-compiler](https://gitlab.gnome.org/GNOME/blueprint-compiler) (`blueprint-compiler` Fedora package)
- [glib-compile-resources](https://gnome.pages.gitlab.gnome.org/gtkmm-documentation/sec-gio-resource.html) (part of the `glib2-devel` Fedora package)

Installing those packages in a Fedora distrobox and running `distrobox-export` seems to work with only minor issues (you may want/need to install `vte291-gtk4-devel` and `webkitgtk6.0-devel` in the distrobox to make blueprint-compiler happy)

## Built With

- [PyGObject](https://pygobject.gnome.org/) - Python bindings for [GTK4](https://docs.gtk.org/gtk4/overview.html) and [Libadwaita](https://gnome.pages.gitlab.gnome.org/libadwaita/doc/main/)
- [Blueprint](https://gnome.pages.gitlab.gnome.org/blueprint-compiler/) - Markup for GTK4 interfaces
- [GNOME VTE library](https://gitlab.gnome.org/GNOME/vte) - Embeddable terminal component
- [WebKitGTK](https://webkitgtk.org/) - Embeddable WebKit component (used to display changelogs)
- [Python-Markdown](https://python-markdown.github.io/) - Convert markdown to HTML
- [github-markdown-css](https://cdnjs.com/libraries/github-markdown-css) - CSS library for markdown converted to HTML
- [PyYAML](https://pyyaml.org/) - Python YAML framework

## Authors

Just me so far.

## License

This project is licensed under the GPL-3.0 or newer license, see [LICENSE](license) for details.

## Acknowledgements

- The Bazzite team, specifially the [Bazzite Portal author](https://github.com/xXJSONDeruloXx), whoever wrote `bazzite-rollback-helper`, and Zach on the Bazzite discord.
