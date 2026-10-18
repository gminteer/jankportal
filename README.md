# Jank Portal

A Clone of [Bazzite Portal](https://github.com/xXJSONDeruloXx/yafti-gtk), also using Python and GTK, but not directly based off of it. The project started mostly as an excuse to get back into Python / learn how to make a Python app with a GUI that isn't Tkinter. It more or less works, and adds a wrapper around `ostree`, `rpm-ostree` and `bazzite-rollback-helper` for some common tasks (in the `Deployments` tab).

## Things it does that Portal don't

- A simple wrapper around wrangling deployments, that lets you:
  - pin/unpin deployments
  - rebase to a different image/tag (with constraints, it won't let you jump to a different desktop or add/remove the nvidia driver without changing settings)
  - rebase to a specific version you currently have deployed
  - remove overlaid packages on the booted deployment.

- Joystick input support. Possibly a bit janky, but it seems to work and ticks all of the boxes I had for it:
  - Bindings are displayed in the UI when at least one joystick is connected
  - Joystick connect/disconnect events are handled
  - Multiple joysticks are supported (JankPortal just listens to all of them)

- Embeds a terminal widget instead of running an external terminal

- Uses GTK Blueprints and is much more webslop brained than `yafti-gtk`'s bash script brained.

- Uses Adwaita and makes a reasonable attempt to follow the GNOME user interface guidelines

## Installation

At some point I'll start actually putting up releases, but until then:

1. Clone this repo
2. Run `./build_distrobox.sh` to assemble a distrobox with all needed dependencies installed.
3. Run `./jankbuild.sh` to build an RPM
4. Use `rpm-ostree` to install the resulting RPM, and reboot.

## Built With

- [uv](https://docs.astral.sh/uv/) - Everyone loves it and it seems like it's pretty good
- [hatchling](https://hatch.pypa.io/latest/) - Because I need a build hook and `uv`'s default backend doesn't have them
- [PyGObject](https://pygobject.gnome.org/) - Python bindings for [GTK4](https://docs.gtk.org/gtk4/overview.html) and [Libadwaita](https://gnome.pages.gitlab.gnome.org/libadwaita/doc/main/), which are surprisingly decent
- [Blueprint](https://gnome.pages.gitlab.gnome.org/blueprint-compiler/) - Markup for GTK4 interfaces, I just wish the blueprint guy went further and I could use Blueprints at runtime with tag strings or something.
- [GNOME VTE library](https://gitlab.gnome.org/GNOME/vte) - Virtual terminal component, because embedding a terminal feels a lot slicker than running `$DEFAULT_TERMINAL`
- [WebKitGTK](https://webkitgtk.org/), [Python-Markdown](https://python-markdown.github.io/), and [github-markdown-css](https://cdnjs.com/libraries/github-markdown-css) - WebKit component, the easiest way to show markdown in a GTK app is converting to HTML and embedding a WebView?
- [PyYAML](https://pyyaml.org/) - Read YAML files
- [tomli-w](https://github.com/hukkin/tomli-w) - Write TOML files (kind of surprised the built-in tomllib is only a reader)

## Authors

Just me ("h3lmut" on the Bazzite discord) so far

## License

This project is licensed under the GPL-3.0 or newer license, see [LICENSE](license) for details.

## Acknowledgements

- The Bazzite team, specifically the [Bazzite Portal author](https://github.com/xXJSONDeruloXx), whoever wrote `bazzite-rollback-helper`, and Zach on the Bazzite discord.
- [PromptFont](https://shinmera.com/promptfont) by Shinmera (Yukari Hafner)
- [ComicShannsMono Nerd Font](https://github.com/jesusmgg/comic-shanns-mono)
