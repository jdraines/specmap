from __future__ import annotations

import os

from hatchling.builders.hooks.plugin.interface import BuildHookInterface


class CustomBuildHook(BuildHookInterface):
    PLUGIN_NAME = "custom"

    def initialize(self, version, build_data):
        web_dist = os.path.join(self.root, "..", "web", "dist")
        if os.path.isdir(web_dist):
            build_data["force_include"][web_dist] = "specmap/_static"
