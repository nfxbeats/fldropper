"""User-supplied plugin preset locations, relative to the FL Studio content root.

Plugin-specific formats are declared separately from shared FST presets.
"""

PLUGIN_PRESETS = (
    ("autogun", "Autogun", "Generators", "Autogun"),
    ("directwave", "DirectWave", "Generators", "DirectWave"),
    ("fpc", "FPC", "Generators", "FPC"),
    ("harmless", "Harmless", "Generators", "Harmless"),
    ("harmor", "Harmor", "Generators", "Harmor"),
    ("kepler-exo", "Kepler EXO", "Generators", "Kepler Exo"),
    ("minisynth", "MiniSynth", "Generators", "MiniSynth"),
    ("morphine", "Morphine", "Generators", "Morphine"),
    ("ogun", "Ogun", "Generators", "Ogun"),
    ("patcher", "Patcher (Effect)", "Effects", "Patcher"),
    ("patcher-generator", "Patcher (Generator)", "Generators", "Patcher"),
    ("poizone", "PoiZone", "Generators", "PoiZone"),
    ("sawer", "Sawer", "Generators", "Sawer"),
    ("sytrus", "Sytrus", "Generators", "Sytrus"),
    ("toxic-biohazard", "Toxic Biohazard", "Generators", "Toxic Biohazard"),
    ("transistor-bass", "Transistor Bass", "Generators", "Transistor Bass"),
    ("wave-candy", "Wave Candy", "Effects", "Wave Candy"),
)

CHANNEL_PRESETS = (("3x-osc", "3x Osc channel states", "Data/Patches/Channel presets/3x Osc"),)

PLUGIN_EXTENSIONS = {"morphine": (".fst", ".mrp"), "toxic-biohazard": (".fst", ".txd", ".tbio"),
                     "poizone": (".fst", ".fxp"), "sawer": (".fst", ".sawer")}
NATIVE_PRESET_PLUGINS = {ext: name for id, name, _, _ in PLUGIN_PRESETS
                         for ext in PLUGIN_EXTENSIONS.get(id, ()) if ext not in (".fst", ".fxp")}

# Measured from the user-identified PoiZone ABS Abysmal ARP.fxp sample.
FXP_PLUGIN_IDS = {b"SawW": ("PoiZone", "generator")}

CATALOG_REVISION = 13
