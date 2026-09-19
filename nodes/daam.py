"""Cross attention capture (DAAM) and per tag exploration."""

import logging
import math
import os
import random
import re

import numpy as np
import torch
from PIL import Image
import torch.nn.functional as F

import comfy.sample
import comfy.utils
import folder_paths
import latent_preview


#################################################################
# Prompt tags
#################################################################
# The HEATMAP type passed between the two nodes is
# {latent_index: tensor(tokens, map_h, map_w)}, averaged over all attention
# layers and sampling steps. Splitting the prompt into tags is what turns that
# token axis into something a reader can point at.

# Shown for a token that carries an embedding tensor rather than a vocabulary
# id, when its name could not be recovered.
EMBEDDING_TEXT = "[emb]"

# Tokenizing replaces "embedding:name" with raw vectors, which drops the name,
# so tokenize_break() stashes the names under a key no tokenizer stream uses.
EMBEDDING_NAMES_KEY = "_daam_embedding_names"

# Keyword that starts a new 77 token chunk, as in ComfyUI-ppm.
BREAK_SEPARATOR = "BREAK"
EMBEDDING_PATTERN = re.compile(r"embedding:([^\s,;()\[\]]+)")


def _tokenizer_key(tokens: dict) -> str:
    """Pick the token stream the heat maps are aligned to."""
    for key in ("l", "t5xxl"):
        if key in tokens:
            return key
    # Keys starting with "_" are our own metadata, not tokenizer streams.
    return next(key for key in tokens if not str(key).startswith("_"))


def _inv_vocab(clip, key: str) -> dict:
    """id -> text for one stream, e.g. clip_l's vocabulary for the "l" stream."""
    attr = {"l": "clip_l", "g": "clip_g"}.get(key, key)
    tokenizer = getattr(clip.tokenizer, attr, clip.tokenizer)
    return getattr(tokenizer, "inv_vocab", None) or {}


def _flatten(tokens: dict, key: str) -> list:
    """Flatten the 77 token chunks into one list, keeping their order."""
    return [token for chunk in tokens[key] for token in chunk]


def _special_ids(clip, key: str) -> set:
    """Start/end/padding ids, derived by tokenizing an empty prompt."""
    empty = clip.tokenize("")[key][0]
    special = {0}
    for position in (0, 1, -1):
        try:
            special.add(empty[position][0])
        except IndexError:
            pass
    return special


def _comma_ids(clip, key: str, special: set) -> set:
    """Ids that a bare comma tokenizes to, used as the tag separator."""
    return {token[0] for token in clip.tokenize(",")[key][0]} - special


def tokenize_break(clip, text: str) -> dict:
    """Tokenize a BREAK separated prompt the way CLIPTextEncodeBREAK encodes it.

    Each chunk is tokenized on its own and the chunks are kept in order, which
    is what makes the token axis line up with the concatenated conditioning.
    """
    chunks = [chunk.strip() for chunk in text.split(BREAK_SEPARATOR)]
    chunks = [chunk for chunk in chunks if chunk] or [""]

    tokens_out = {}
    embedding_names = []
    for chunk in chunks:
        embedding_names.extend(EMBEDDING_PATTERN.findall(chunk))
        for key, chunk_tokens in clip.tokenize(chunk).items():
            tokens_out.setdefault(key, []).extend(chunk_tokens)

    if embedding_names:
        tokens_out[EMBEDDING_NAMES_KEY] = embedding_names
    return tokens_out


def split_tags(clip, tokens: dict) -> list:
    """Split the prompt into comma separated tags.

    Returns (tag_text, token_indices) per tag, where the indices address the
    token axis of the heat maps.
    """
    key = _tokenizer_key(tokens)
    special = _special_ids(clip, key)
    separators = _comma_ids(clip, key, special)
    if not separators:
        return []

    inv_vocab = _inv_vocab(clip, key)
    names = iter(tokens.get(EMBEDDING_NAMES_KEY) or [])

    tags = []
    idxs, text, depth, in_embedding, index = [], "", 0, False, -1

    def flush():
        nonlocal idxs, text
        if idxs:
            # Fall back to positions so a token the vocabulary cannot name does
            # not make the tag disappear entirely.
            tag = text.strip().rstrip(",").strip() or f"tokens {idxs[0]}-{idxs[-1]}"
            tags.append((tag, idxs))
        idxs, text = [], ""

    for chunk in tokens[key]:
        for token in chunk:
            index += 1
            token_id = token[0]

            # "embedding:name" puts raw vectors on the token axis instead of
            # vocabulary ids. They are prompt content, never markers.
            if not isinstance(token_id, int):
                idxs.append(index)
                if not in_embedding:
                    # One label is enough for a multi vector embedding.
                    in_embedding = True
                    name = next(names, None)
                    text += f"{EMBEDDING_TEXT} {name}" if name else EMBEDDING_TEXT
                continue

            in_embedding = False
            if token_id in special:
                continue
            # A comma separates tags only at the top level: inside a weight
            # group like "(a,b:-1)" it belongs to the tag.
            if token_id in separators and depth == 0:
                flush()
                continue

            idxs.append(index)
            piece = inv_vocab.get(token_id, "").replace("</w>", " ")
            text += piece

            depth = max(0, depth + piece.count("(") - piece.count(")"))
            # BPE glues a comma onto the preceding character, so ")," is a
            # single token the separator ids never match. Close on the decoded
            # text instead, once the parens it opened are balanced again.
            if depth == 0 and piece.strip().endswith(","):
                flush()

        # A tag never spans two 77 token chunks: the boundary ends it.
        flush()

    return tags


def _split_diagnostics(clip, tokens: dict) -> str:
    """Explain why split_tags() came back empty."""
    try:
        key = _tokenizer_key(tokens)
        special = _special_ids(clip, key)
        separators = _comma_ids(clip, key, special)
        flat = _flatten(tokens, key)
        content = [t for t in flat if t[0] not in special and t[0] not in separators]
        return (
            f"keys={list(tokens)} used={key} chunks={len(tokens[key])} "
            f"tokens={len(flat)} content_tokens={len(content)} "
            f"special={sorted(special)} separators={sorted(separators)} "
            f"first_ids={[t[0] for t in flat[:12]]}"
        )
    except Exception as error:
        return f"(diagnostics failed: {error})"


#################################################################
# Structure scores
#################################################################
# Whether a tag's heat map has a shape at all, and how strongly. Two shapes
# matter and no single reading ranks them fairly: z-scoring fixes a map's total
# energy, so peak height and spread area are two ends of one seesaw. Sharpness
# favours the small and deep (an eye), separability the large and cleanly
# bounded (a body), and a tag counts by whichever it does better on.
#
# Both readings are absolute, so each is scored against a fixed floor and
# ceiling rather than against the other tags in the render: a render where
# every tag stays grey really did build nothing, and two renders compare tag
# for tag. The bounds come from 222 tags over six renders -- floors near the
# 25th percentile of each reading, where a map stops having a visible shape,
# ceilings near the 95th.
SHARP_FLOOR, SHARP_CEILING = 3.5, 8.0
SPLIT_FLOOR, SPLIT_CEILING = 0.68, 0.80

# Cells taken for the sharpness reading. One cell is noise, and a tag that
# landed on both arms should not score below one that landed on a single arm.
SHARP_FRACTION = 0.01


def _sharpness(maps: np.ndarray) -> np.ndarray:
    """Mean |z| over the strongest cells of each map.

    On the z-scored map, so the large positive baseline every attention map
    carries drops out; absolute, because a tag can just as well carve a dark
    region as light a bright one. Attention is non-negative, so the two are
    mutually exclusive: the floor sits at -mean/std, and only a map with no
    peak can have a deep hole.
    """
    flat = maps.reshape(maps.shape[0], -1)
    mean = flat.mean(1, keepdims=True)
    std = flat.std(1, keepdims=True) + 1e-12
    deviation = np.abs((flat - mean) / std)
    keep = max(1, round(deviation.shape[1] * SHARP_FRACTION))
    return np.sort(deviation, 1)[:, -keep:].mean(1)


def _separability(maps: np.ndarray) -> np.ndarray:
    """Otsu's between-class variance ratio for each map.

    Scale free by construction: a clean edge scores the same whether it
    encloses an eye or a whole body, which is exactly where a peak reading
    fails.
    """
    flat = np.sort(maps.reshape(maps.shape[0], -1), 1)
    count = flat.shape[1]
    cumulative = np.cumsum(flat, 1)
    total = cumulative[:, -1:]

    index = np.arange(1, count)
    weight = index / count
    below = cumulative[:, :-1] / index
    above = (total - cumulative[:, :-1]) / (count - index)
    between = weight * (1 - weight) * (above - below) ** 2

    variance = flat.var(1) + 1e-12
    return between.max(1) / variance


def _credit(values, floor, ceiling):
    """How far past the floor a reading got, as 0..1."""
    return np.clip((values - floor) / (ceiling - floor), 0, 1)


def structure_scores(stacked: np.ndarray) -> list:
    """Per tag: did this tag give the picture a shape, and how strongly.

    One 0..1 credit per tag, where 0 means the map is as shapeless as the two
    readings can tell and 1 means it is as strong as they measure.
    """
    credit = np.maximum(
        _credit(_sharpness(stacked), SHARP_FLOOR, SHARP_CEILING),
        _credit(_separability(stacked), SPLIT_FLOOR, SPLIT_CEILING),
    )
    return [float(value) for value in credit]


#################################################################
# Attention capture
#################################################################
# Cross attention maps only exist while sampling runs, so they have to be
# collected from inside the UNet. The patcher below replaces every attn2 block
# for the duration of one sample call and accumulates the maps it sees.


def _locate_attn2_blocks(diffusion_model):
    """Every (block_name, block_index, transformer_index) carrying an attn2."""
    tags = []

    def walk(name, blocks):
        for index, block in enumerate(blocks):
            for module in block.modules():
                if module.__class__.__name__ == "SpatialTransformer":
                    for transformer_index in range(len(module.transformer_blocks)):
                        tags.append((name, index, transformer_index))

    walk("input", diffusion_model.input_blocks)
    if getattr(diffusion_model, "middle_block", None) is not None:
        walk("middle", [diffusion_model.middle_block])
    walk("output", diffusion_model.output_blocks)

    return tags


class CrossAttentionCollector:
    """Collects per token cross attention maps during sampling."""

    def __init__(self, model_patcher, img_height, img_width, collect_pos, collect_neg):
        self.model_patcher = model_patcher
        self.img_height = img_height
        self.img_width = img_width
        self.enabled = {"pos": collect_pos, "neg": collect_neg}

        # side -> batch_index -> (tokens, h, w) running sum, plus a count so the
        # layers and timesteps can be averaged at the end. Accumulating in place
        # keeps memory flat no matter how many steps are sampled.
        self.sums = {"pos": {}, "neg": {}}
        self.counts = {"pos": {}, "neg": {}}

        # Common grid the per layer maps are resampled onto. image/16 is the
        # finest grid SDXL attends at (latent/2), so those layers land without
        # loss and the deeper latent/4 layers upscale by an exact factor of 2.
        self.map_h = max(1, img_height // 16)
        self.map_w = max(1, img_width // 16)

    def patch(self):
        self.tags = _locate_attn2_blocks(self.model_patcher.model.diffusion_model)
        self.saved_options = self.model_patcher.model_options.copy()
        for name, index, transformer_index in self.tags:
            self.model_patcher.set_model_patch_replace(
                self._attn2, "attn2", name, index, transformer_index
            )

    def unpatch(self):
        for name, index, transformer_index in getattr(self, "tags", []):
            self.model_patcher.set_model_patch_replace(
                None, "attn2", name, index, transformer_index
            )
        if getattr(self, "saved_options", None) is not None:
            self.model_patcher.model_options = self.saved_options.copy()

    def _attn2(self, q, context=None, value=None, extra_options={}, mask=None):
        heads = extra_options["n_heads"]
        k = context
        v = value if value is not None else context

        batch, q_len, inner = q.shape
        dim_head = inner // heads

        def split(t):
            return t.view(t.shape[0], t.shape[1], heads, dim_head).transpose(1, 2)

        qh, kh, vh = split(q), split(k), split(v)

        # The heat maps are the attention probabilities themselves, so this uses
        # a plain attention instead of a fused kernel that never exposes them.
        scale = 1.0 / math.sqrt(dim_head)
        scores = torch.matmul(qh, kh.transpose(-2, -1)) * scale
        if mask is not None:
            scores = scores + mask
        probs = scores.softmax(dim=-1)  # (batch, heads, q_len, tokens)

        out = torch.matmul(probs, vh)
        out = out.transpose(1, 2).reshape(batch, q_len, inner)

        try:
            self._collect(probs, extra_options.get("cond_or_uncond", [0]))
        except Exception as error:  # never break sampling over a heat map
            logging.warning(f"[DAAM] attention collection skipped: {error}")

        return out

    def _collect(self, probs, cond_or_uncond):
        batch = probs.shape[0]
        q_len = probs.shape[2]

        # Recover the latent grid this attention layer works on.
        ratio = (q_len / (self.img_height * self.img_width)) ** 0.5
        h = int(round(self.img_height * ratio))
        w = int(round(self.img_width * ratio))
        if h * w != q_len or h == 0 or w == 0:
            return

        # cond_or_uncond lists what the batch holds, in batch order:
        # 0 = conditional, 1 = unconditional. Relying on it rather than on
        # tensor shapes keeps this correct whether ComfyUI batches cond and
        # uncond together or runs them separately.
        groups = max(1, len(cond_or_uncond))
        group_size = max(1, batch // groups)

        for index in range(batch):
            side = (
                "neg"
                if cond_or_uncond[min(index // group_size, groups - 1)] == 1
                else "pos"
            )
            if not self.enabled[side]:
                continue

            latent_index = index % group_size

            # (heads, q_len, tokens) -> (tokens, heads, h, w)
            maps = probs[index].permute(2, 0, 1).reshape(-1, 1, h, w).float()
            maps = F.interpolate(maps, size=(self.map_h, self.map_w), mode="bicubic")
            tokens = probs.shape[-1]
            maps = maps.view(tokens, -1, self.map_h, self.map_w).mean(1)

            store = self.sums[side]
            if latent_index in store:
                store[latent_index] += maps
            else:
                store[latent_index] = maps
            self.counts[side][latent_index] = self.counts[side].get(latent_index, 0) + 1

    def heatmaps(self, side):
        """{latent_index: tensor(tokens, map_h, map_w)}, or None when disabled."""
        if not self.enabled[side] or not self.sums[side]:
            return None

        return {
            latent_index: (total / max(1, self.counts[side][latent_index]))
            # Only now does this leave the GPU: doing it per block would sync
            # on every attention layer of every step.
            .cpu()
            for latent_index, total in self.sums[side].items()
        }


#################################################################
# Nodes
#################################################################
def _output_connected(prompt, node_id, output_index) -> bool:
    """Whether anything consumes this node's output, so work can be skipped."""
    if not prompt or node_id is None:
        return True

    for other_id, other in prompt.items():
        if str(other_id) == str(node_id):
            continue
        for value in other.get("inputs", {}).values():
            if isinstance(value, list) and len(value) == 2:
                if str(value[0]) == str(node_id) and value[1] == output_index:
                    return True
    return False


class DAAMSamplerCustom:
    """SamplerCustom that also captures cross attention heatmaps."""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "model": ("MODEL",),
                "add_noise": ("BOOLEAN", {"default": True}),
                "noise_seed": (
                    "INT",
                    {
                        "default": 0,
                        "min": 0,
                        "max": 0xFFFFFFFFFFFFFFFF,
                        "control_after_generate": True,
                    },
                ),
                "cfg": (
                    "FLOAT",
                    {
                        "default": 8.0,
                        "min": 0.0,
                        "max": 100.0,
                        "step": 0.1,
                        "round": 0.01,
                    },
                ),
                "positive": ("CONDITIONING",),
                "negative": ("CONDITIONING",),
                "sampler": ("SAMPLER",),
                "sigmas": ("SIGMAS",),
                "latent_image": ("LATENT",),
            },
            "hidden": {"node_id": "UNIQUE_ID", "prompt": "PROMPT"},
        }

    RETURN_TYPES = ("LATENT", "LATENT", "HEATMAP", "HEATMAP")
    RETURN_NAMES = ("output", "denoised_output", "pos_heatmaps", "neg_heatmaps")
    FUNCTION = "sample"

    CATEGORY = "DaamPack/DAAM"
    DESCRIPTION = (
        "SamplerCustom with DAAM attention capture. Patches the UNet's cross "
        "attention for the duration of the sampling pass."
    )

    def sample(
        self,
        model,
        add_noise,
        noise_seed,
        cfg,
        positive,
        negative,
        sampler,
        sigmas,
        latent_image,
        node_id=None,
        prompt=None,
    ):
        latent = latent_image.copy()
        samples_in = comfy.sample.fix_empty_latent_channels(model, latent["samples"])
        latent["samples"] = samples_in

        _, _, lh, lw = samples_in.shape
        collector = CrossAttentionCollector(
            model,
            img_height=lh * 8,
            img_width=lw * 8,
            collect_pos=_output_connected(prompt, node_id, 2),
            collect_neg=_output_connected(prompt, node_id, 3),
        )

        # Capturing attention means replacing ComfyUI's optimised kernels, so
        # skip it entirely when no heatmap output is connected. The node then
        # costs exactly what SamplerCustom costs.
        collecting = collector.enabled["pos"] or collector.enabled["neg"]

        if collecting:
            collector.patch()
        try:
            out, out_denoised = self._sample_custom(
                model,
                add_noise,
                noise_seed,
                cfg,
                positive,
                negative,
                sampler,
                sigmas,
                latent,
            )
        finally:
            if collecting:
                collector.unpatch()

        return (
            out,
            out_denoised,
            collector.heatmaps("pos"),
            collector.heatmaps("neg"),
        )

    def _sample_custom(
        self,
        model,
        add_noise,
        noise_seed,
        cfg,
        positive,
        negative,
        sampler,
        sigmas,
        latent,
    ):
        """SamplerCustom's own sampling pass, unchanged."""
        # Imported here because comfy_extras is not importable while custom
        # nodes are still being loaded.
        from comfy_extras.nodes_custom_sampler import (
            Noise_EmptyNoise,
            Noise_RandomNoise,
        )

        samples_in = latent["samples"]
        noise = (
            Noise_RandomNoise(noise_seed).generate_noise(latent)
            if add_noise
            else Noise_EmptyNoise().generate_noise(latent)
        )

        x0_output = {}
        callback = latent_preview.prepare_callback(
            model, sigmas.shape[-1] - 1, x0_output
        )

        samples = comfy.sample.sample_custom(
            model,
            noise,
            cfg,
            sampler,
            sigmas,
            positive,
            negative,
            samples_in,
            noise_mask=latent.get("noise_mask"),
            callback=callback,
            disable_pbar=not comfy.utils.PROGRESS_BAR_ENABLED,
            seed=noise_seed,
        )

        out = latent.copy()
        out["samples"] = samples

        if "x0" in x0_output:
            out_denoised = latent.copy()
            out_denoised["samples"] = model.model.process_latent_out(
                x0_output["x0"].cpu()
            )
        else:
            out_denoised = out

        return out, out_denoised


class DAAMTagExplorer:
    """Interactive per tag attention explorer."""

    def __init__(self):
        self.output_dir = folder_paths.get_temp_directory()
        self.type = "temp"
        self.prefix_append = "_temp_" + "".join(
            random.choice("abcdefghijklmnopqrstuvwxyz") for _ in range(5)
        )

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "clip": (
                    "CLIP",
                    {"tooltip": "The CLIP model that encoded the prompt."},
                ),
                "text": (
                    "STRING",
                    {
                        "multiline": True,
                        "forceInput": True,
                        "tooltip": (
                            "The same prompt that was encoded for sampling, "
                            "BREAK separators included."
                        ),
                    },
                ),
                "heatmaps": (
                    "HEATMAP",
                    {"tooltip": "pos_heatmaps from 'Sampler Custom (DAAM)'."},
                ),
                "images": ("IMAGE", {"tooltip": "The decoded images."}),
            },
        }

    RETURN_TYPES = ()
    FUNCTION = "explore"
    OUTPUT_NODE = True

    CATEGORY = "DaamPack/DAAM"
    DESCRIPTION = (
        "Hover the image for a per tag attention bar chart, then click tags to "
        "overlay their heatmap. Several pinned tags show as one map."
    )

    def explore(self, clip, text, heatmaps, images):
        if not heatmaps:
            raise RuntimeError(
                "DAAM: no attention heat maps were collected during sampling. "
                "Check that 'heatmaps' comes from 'Sampler Custom (DAAM)'."
            )

        tokens = tokenize_break(clip, text)
        tags = split_tags(clip, tokens)
        if not tags:
            raise RuntimeError(
                "DAAM: could not split the prompt into tags. "
                + _split_diagnostics(clip, tokens)
            )

        saved_images, saved_maps, structure, labels = [], [], [], []

        for batch_index in range(images.shape[0]):
            heat_map = heatmaps.get(batch_index)
            if heat_map is None:
                continue

            batch_labels, maps = self._tag_maps(tags, heat_map)
            if not maps:
                continue
            labels = batch_labels

            # Shipped at their native grid (image/16) for the browser to
            # upscale: full resolution maps for every tag would be hundreds of
            # megabytes, while this is a few hundred kilobytes and lets the bar
            # chart and the overlay update without a server round trip.
            stacked = torch.stack(maps, 0).detach().cpu().numpy().astype(np.float32)

            # The panel draws the first image of the batch, so that is the one
            # whose structure scores it needs.
            if not structure:
                structure = structure_scores(stacked)

            image = images[batch_index]
            saved_images.append(self._save_image(image, batch_index))
            saved_maps.append(self._save_tag_maps(stacked, image, batch_index))

        # Deliberately not "images": that key makes ComfyUI render its own
        # preview under the node, duplicating the canvas we draw ourselves.
        return {
            "ui": {
                "tag_images": saved_images,
                "tag_maps": saved_maps,
                "tags": labels,
                "tag_structure": structure,
            }
        }

    @staticmethod
    def _tag_maps(tags, heat_map):
        """One averaged map per tag whose tokens the heat map actually holds."""
        token_count = heat_map.shape[0]

        labels, maps = [], []
        for tag, token_idxs in tags:
            valid = [i for i in token_idxs if i < token_count]
            if valid:
                labels.append(tag)
                maps.append(heat_map[valid].mean(0))
        return labels, maps

    def _save_path(self, image, batch_index, suffix):
        prefix = "DAAMTagExplorer" + self.prefix_append
        full_output_folder, filename, counter, subfolder, _ = (
            folder_paths.get_save_image_path(
                prefix, self.output_dir, image.shape[1], image.shape[0]
            )
        )
        name = filename.replace("%batch_num%", str(batch_index))
        file = f"{name}_{counter:05}{suffix}"
        return os.path.join(full_output_folder, file), {
            "filename": file,
            "subfolder": subfolder,
            "type": "temp",
        }

    def _save_image(self, image, batch_index):
        path, entry = self._save_path(image, batch_index, ".png")
        array = (255.0 * image.cpu().numpy()).clip(0, 255).astype(np.uint8)
        Image.fromarray(array).save(path, compress_level=1)
        return entry

    def _save_tag_maps(self, stacked, image, batch_index):
        path, entry = self._save_path(image, batch_index, "_tagmaps.npy")
        np.save(path, stacked)
        return entry
