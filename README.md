# Jank Portal

A Clone of [Bazzite Portal](https://github.com/xXJSONDeruloXx/yafti-gtk), also using Python and GTK, but not directly based off of it. The project started mostly as an excuse to get back into Python, and learn a GUI toolkit that isn't Tkinter along the way. It's mostly functional, and incorporates a partially implemented wrapper around `rpm-ostree` and `bazzite-rollback-helper` in the deployments tab, but it's definitely not ready for prime time yet.

## Things it does that Portal don't

- A simple wrapper around wrangling deployments, that lets you pin/unpin `rpm-ostree` images, rebase to a different image/tag (with constraints, it won't let you jump to a different desktop or add/remove the nvidia driver currently), and/or rebase to a specific version you currently have deployed.

- Joystick input support. Currently fairly janky: the joystick needs to have been plugged in at program launch, and it doesn't handle disconnect/connect events at all, and there's no UI hints on the controller bindings yet:
  - Left stick/dpad = move selected widget
  - Left bumper is shift-tab, right bumper is tab
  - South button selects
  - East button cancels
  - North button selects search entry (in the hopes that will trigger on-screen keyboard)
  - Left/right triggers swap to previous/next page
  - Right stick Y-axis scrolls
  - Start button opens about menu

- Embeds a terminal widget instead of running an external terminal

- Uses GTK Blueprints and is much more webslop brained than `yafti-gtk`'s bash script brained.

- Uses Adwaita and makes a reasonable attempt to follow the GNOME user interface guidelines

## Installation

At some point I'll start actually putting up releases, but until then:

1. Clone this repo
2. Run `./build_distrobox.sh` to assemble a distrobox with all needed dependencies installed.
3. Run `./jankbuild.sh` to build an RPM
4. Use `rpm-ostree` to install the resulting RPM, and reboot.
5. Get annoyed that I haven't bundled an .desktop file yet so you have to run `jankportal` in a terminal or make your own launch menu entry for it.

## Built With

- [uv](https://docs.astral.sh/uv/) - Everyone loves it and it seems like it's pretty good
- [hatchling](https://hatch.pypa.io/latest/) - Because I need a build hook and `uv` doesn't have them
- [PyGObject](https://pygobject.gnome.org/) - Python bindings for [GTK4](https://docs.gtk.org/gtk4/overview.html) and [Libadwaita](https://gnome.pages.gitlab.gnome.org/libadwaita/doc/main/), which are surprisingly decent
- [Blueprint](https://gnome.pages.gitlab.gnome.org/blueprint-compiler/) - Markup for GTK4 interfaces, I just wish the blueprint guy went further and I could tag strings in python and get blobs of GTK widgets
- [GNOME VTE library](https://gitlab.gnome.org/GNOME/vte) - Virtual terminal component, because embedding a terminal feels a lot slicker than running `$DEFAULT_TERMINAL`
- [WebKitGTK](https://webkitgtk.org/) - WebKit component, because the best way to show markdown in a GTK app is converting markdown to HTML and embedding a Webkit WebView?
- [Python-Markdown](https://python-markdown.github.io/) - Convert markdown to HTML
- [github-markdown-css](https://cdnjs.com/libraries/github-markdown-css) - Make markdown look like it does on GitHub
- [PyYAML](https://pyyaml.org/) - Read YAML files

## Authors

Just me ("h3lmut" on the Bazzite discord) so far

## License

This project is licensed under the GPL-3.0 or newer license, see [LICENSE](license) for details.

## Acknowledgements

- The Bazzite team, specifically the [Bazzite Portal author](https://github.com/xXJSONDeruloXx), whoever wrote `bazzite-rollback-helper`, and Zach on the Bazzite discord.
- [PromptFont](https://shinmera.com/promptfont) by Shinmera (Yukari Hafner)
