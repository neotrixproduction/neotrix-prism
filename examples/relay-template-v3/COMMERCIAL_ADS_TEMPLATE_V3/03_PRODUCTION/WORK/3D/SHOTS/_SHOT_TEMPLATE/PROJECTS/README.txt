03_PRODUCTION/WORK/3D/SHOTS/_SHOT_TEMPLATE/PROJECTS

Editable shot projects organized by stage:
MODELLING - Shot-specific modelling and geometry work. Reusable models belong in 3D/ASSETS.
RIGGING - Shot-specific rigs, controls, and deformation setup.
LAYOUT - Shot cameras, composition, staging, and rough timing.
ANIMATION - Shot character, object, and camera animation.
FX - Editable shot simulation and effects setups. Generated caches belong in the shot CACHE folder.
LIGHTING - Shot lighting, materials, look development, and render setup.
COMPOSITING - Editable shot composites combining renders, footage, and effects.
OTHERS - Other editable shot work that does not fit a named stage.

Use one increasing 3D scene-save version sequence across all stages in this shot. Do not restart at v001 in each stage. Direct render versions match the producing scene. Preserve earlier saves and outputs.

Example progression: MODELLING/HVN_Vertical_0010_v001.blend, LAYOUT/HVN_Vertical_0010_v002.blend, LIGHTING/HVN_Vertical_0010_v003.blend. Lighting v003 renders to the shot RENDERS/v003.

Compositing save versions advance independently of 3D. Outputs belong in the shot COMPOSITING/renders/vNNN/frames or preview, outside PROJECTS.

Keep existing general saves directly in PROJECTS when needed. Do not relocate existing work without checking dependencies. Reusable assets belong in 3D/ASSETS. Work in a renamed shot copy, never in _SHOT_TEMPLATE.
