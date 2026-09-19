"""The ComfyUI modules the pack imports are stubbed so it imports outside
ComfyUI; nothing else is faked. Only the sampler node calls into them.
"""

import sys
import types
import importlib
from pathlib import Path

import pytest
from aiohttp import web

PACK_DIR = Path(__file__).resolve().parent.parent
PACK_NAME = "daam_pack"


@pytest.fixture(scope="session")
def temp_dir(tmp_path_factory):
    return tmp_path_factory.mktemp("temp")


@pytest.fixture(scope="session")
def daam(temp_dir):
    """The node module, imported the way ComfyUI would."""
    for name in ("comfy", "comfy.sample", "comfy.utils", "latent_preview"):
        sys.modules[name] = types.ModuleType(name)
    sys.modules["comfy"].sample = sys.modules["comfy.sample"]
    sys.modules["comfy"].utils = sys.modules["comfy.utils"]

    # Functional, so that a node saving previews the usual way would leave
    # files in temp_dir for the tests to find.
    def get_save_image_path(prefix, output_dir, width=0, height=0):
        counter = len(list(Path(output_dir).iterdir())) + 1
        return output_dir, prefix, counter, "", prefix

    folder_paths = types.ModuleType("folder_paths")
    folder_paths.get_temp_directory = lambda: str(temp_dir)
    folder_paths.get_save_image_path = get_save_image_path
    sys.modules["folder_paths"] = folder_paths

    server = types.ModuleType("server")
    server.PromptServer = types.SimpleNamespace(
        instance=types.SimpleNamespace(routes=web.RouteTableDef())
    )
    sys.modules["server"] = server

    package = types.ModuleType(PACK_NAME)
    package.__path__ = [str(PACK_DIR)]
    sys.modules[PACK_NAME] = package
    return importlib.import_module(f"{PACK_NAME}.nodes.daam")
