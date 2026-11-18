"""OPTIONAL UE 5.4 EDITOR SCRIPT - generate coloured Spatial Lab materials.

Run inside the Unreal Editor Python console:
  exec(open(r'ABSOLUTE_PATH_TO_PROJECT\\tools\\create_materials_unreal.py').read())

Requires enabling the built-in Python Editor Script Plugin.
No existing asset is deleted or replaced. C++ visualizer works without these.
"""
import unreal

PALETTE = {
    "M_CabbageBody": (0.035, 0.48, 0.27),
    "M_Wheel": (0.013, 0.021, 0.031),
    "M_ToFFront": (0.29, 0.85, 0.40),
    "M_ToFLeft": (0.13, 0.48, 0.88),
    "M_ToFRight": (0.95, 0.43, 0.12),
    "M_Obstacle": (0.07, 0.19, 0.31),
    "M_Floor": (0.012, 0.038, 0.064),
}
ASSET_DIR = "/Game/SpatialLab/Materials"

tools = unreal.AssetToolsHelpers.get_asset_tools()
editor = unreal.EditorAssetLibrary

if not editor.does_directory_exist(ASSET_DIR):
    editor.make_directory(ASSET_DIR)

created, skipped = [], []
for name, rgb in PALETTE.items():
    package = ASSET_DIR + "/" + name
    if editor.does_asset_exist(package):
        skipped.append(name)
        continue
    material = tools.create_asset(name, ASSET_DIR, unreal.Material, unreal.MaterialFactoryNew())
    if not material:
        raise RuntimeError("Failed to create material " + name)
    colour = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionConstant3Vector, -360, 0
    )
    colour.set_editor_property("constant", unreal.LinearColor(*rgb, 1.0))
    if not unreal.MaterialEditingLibrary.connect_material_property(
        colour, "", unreal.MaterialProperty.MP_BASE_COLOR
    ):
        raise RuntimeError("Failed BaseColor connection for " + name)
    roughness = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionConstant, -360, 150
    )
    roughness.set_editor_property("r", 0.74 if name != "M_Wheel" else 0.96)
    unreal.MaterialEditingLibrary.connect_material_property(
        roughness, "", unreal.MaterialProperty.MP_ROUGHNESS
    )
    unreal.MaterialEditingLibrary.recompile_material(material)
    if not editor.save_loaded_asset(material, only_if_is_dirty=False):
        raise RuntimeError("Failed to save material " + name)
    created.append(name)

unreal.log("Spatial Lab palette created: " + ", ".join(created))
unreal.log("Spatial Lab palette skipped existing: " + ", ".join(skipped))
unreal.log("Restart Play session to see colours. Plain cubes remain the fallback.")
