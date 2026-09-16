"""Custom nodes mappings."""

from .nodes.daam import DAAMSamplerCustom, DAAMTagExplorer


NODE_CLASS_MAPPINGS = {
    # DaamPack/DAAM ##################################################################
    "DAAMSamplerCustom": DAAMSamplerCustom,
    "DAAMTagExplorer": DAAMTagExplorer,
}

# A dictionary that contains the friendly/humanly readable titles for the nodes
NODE_DISPLAY_NAME_MAPPINGS = {
    # DaamPack/DAAM ##################################################################
    "DAAMSamplerCustom": "Sampler Custom (DAAM)",
    "DAAMTagExplorer": "DAAM Tag Explorer",
}


WEB_DIRECTORY = "./web/js"
