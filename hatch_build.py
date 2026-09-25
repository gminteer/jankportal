# ruff: noqa
# type: ignore

import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

from hatchling.builders.hooks.plugin.interface import BuildHookInterface


class CustomBuildHook(BuildHookInterface):
    def initialize(self, version: str, build_data: dict[str, Any]):
        # Configuration paths
        resource_dir = Path("ui")
        output_dir = Path("src/jankportal")
        output_dir.mkdir(parents=True, exist_ok=True)

        compiled_ui_files = []

        # 1. Recursively find and compile all .blp files
        for blp_path in resource_dir.rglob("*.blp"):
            # Maintain subdirectory structure for output UI files
            relative_path = blp_path.relative_to(resource_dir)
            ui_path = resource_dir / relative_path.with_suffix(".ui")

            print(f"Compiling blueprint: {blp_path} -> {ui_path}")
            subprocess.run(
                [
                    "blueprint-compiler",
                    "compile",
                    "--output",
                    str(ui_path),
                    str(blp_path),
                ],
                check=True,
            )
            compiled_ui_files.append(ui_path)

        # 2. Dynamically build the gresource.xml file
        gresource_path = resource_dir / "gresource.xml"
        root = ET.Element("gresources")
        gresource_el = ET.SubElement(
            root, "gresource", prefix="/io/github/gminteer/jankportal"
        )

        # Gather all files to include (.ui and .css)
        files_to_include = list(resource_dir.rglob("*.ui")) + list(
            resource_dir.rglob("*.css")
        )

        for file_path in files_to_include:
            # The path inside the XML needs to be relative to the XML file location
            rel_to_resource = file_path.relative_to(resource_dir)
            file_el = ET.SubElement(gresource_el, "file")
            file_el.text = str(rel_to_resource)

        # Write XML file
        tree = ET.ElementTree(root)
        ET.indent(tree, space="  ")
        tree.write(gresource_path, encoding="utf-8", xml_declaration=True)

        # 3. Compile everything into a binary .gresource file
        output_resource_file = output_dir / "resources.gresource"
        print(f"Compiling resources into: {output_resource_file}")
        subprocess.run(
            [
                "glib-compile-resources",
                f"--sourcedir={resource_dir}",
                f"--target={output_resource_file}",
                str(gresource_path),
            ],
            check=True,
        )

        # 4. Cleanup intermediate .ui and .xml files to keep workspace clean
        for ui_file in compiled_ui_files:
            ui_file.unlink(missing_ok=True)
            gresource_path.unlink(missing_ok=True)
