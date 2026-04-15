from __future__ import annotations

import os
import subprocess

from hatchling.builders.hooks.plugin.interface import BuildHookInterface


class CustomBuildHook(BuildHookInterface):
    PLUGIN_NAME = "custom"

    def initialize(self, version, build_data):
        web_dir = os.path.join(self.root, "web")
        web_dist = os.path.join(web_dir, "dist")

        # Build frontend if source exists but dist doesn't
        if not os.path.isdir(web_dist) and os.path.isfile(os.path.join(web_dir, "package.json")):
            self.app.display_info("Building frontend (this may take a moment)...")
            subprocess.run(["npm", "install"], cwd=web_dir, check=True)
            subprocess.run(["npm", "run", "build"], cwd=web_dir, check=True)

        if os.path.isdir(web_dist):
            build_data["force_include"][web_dist] = "specmap/_static"
