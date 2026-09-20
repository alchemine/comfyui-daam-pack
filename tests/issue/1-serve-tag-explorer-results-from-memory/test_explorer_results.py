import io
import asyncio

import numpy as np
import pytest
import torch
from PIL import Image
from aiohttp.test_utils import make_mocked_request

NODE_ID = "7"
TOKENS = 77
HEIGHT, WIDTH = 64, 96
TAGS = [("1girl", [1]), ("long hair", [3, 4]), ("smile", [6])]


@pytest.fixture
def explore(daam, monkeypatch):
    """Runs the explorer the way ComfyUI does: only declared hidden inputs."""
    section = [(0, 1.0)] * TOKENS
    monkeypatch.setattr(daam, "tokenize_break", lambda clip, text: {"l": [section]})
    monkeypatch.setattr(daam, "split_tags", lambda clip, tokens: TAGS)

    collector = daam.CrossAttentionCollector(None, HEIGHT, WIDTH, True, False)
    q_len = (HEIGHT // 16) * (WIDTH // 16)
    collector._collect(torch.rand(1, 2, q_len, TOKENS).softmax(-1), [0])
    heatmaps = collector.heatmaps("pos")

    def run(images, node_id=NODE_ID):
        inputs = {"clip": None, "text": "", "heatmaps": heatmaps, "images": images}
        if "hidden" in daam.DAAMTagExplorer.INPUT_TYPES():
            inputs["unique_id"] = node_id
        return daam.DAAMTagExplorer().explore(**inputs)

    return run


def request_result(daam, kind, node_id):
    request = make_mocked_request(
        "GET", f"/daam/tag_explorer/{kind}?node_id={node_id}", match_info={"kind": kind}
    )
    return asyncio.run(daam.get_explorer_result(request))


def test_writes_nothing_to_temp(explore, temp_dir):
    explore(torch.rand(2, HEIGHT, WIDTH, 3))
    assert list(temp_dir.iterdir()) == []


def test_ui_message_carries_the_node_key(explore):
    ui = explore(torch.rand(2, HEIGHT, WIDTH, 3))["ui"]
    assert ui["tag_key"] == [NODE_ID]
    assert ui["tags"] == [tag for tag, _ in TAGS]
    assert "tag_images" not in ui and "tag_maps" not in ui


def test_route_serves_image_and_maps(daam, explore):
    explore(torch.rand(2, HEIGHT, WIDTH, 3))

    image = request_result(daam, "image", NODE_ID)
    assert image.content_type == "image/png"
    assert Image.open(io.BytesIO(image.body)).size == (WIDTH, HEIGHT)

    maps = np.load(io.BytesIO(request_result(daam, "maps", NODE_ID).body))
    assert maps.shape == (len(TAGS), HEIGHT // 16, WIDTH // 16)


def test_route_404_for_unknown_node(daam, explore):
    explore(torch.rand(1, HEIGHT, WIDTH, 3))
    assert request_result(daam, "image", "unknown").status == 404


def test_rerun_replaces_the_result(daam, explore):
    explore(torch.zeros(1, HEIGHT, WIDTH, 3))
    explore(torch.ones(1, HEIGHT, WIDTH, 3))

    assert list(daam.EXPLORER_RESULTS) == [NODE_ID]
    image = Image.open(io.BytesIO(request_result(daam, "image", NODE_ID).body))
    assert image.getpixel((0, 0)) == (255, 255, 255)
