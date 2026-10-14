SHOT WORKFLOW

1. Copy the shot template
In File Explorer, copy _SHOT_TEMPLATE inside SHOTS. Rename the copy HVN_Vertical_0010. Leave the template empty.

2. Save the scene by stage
Save editable shot sources inside PROJECTS/MODELLING, RIGGING, LAYOUT, ANIMATION, FX, LIGHTING, COMPOSITING, or OTHERS. Example: PROJECTS/LAYOUT/HVN_Vertical_0010_v001.blend. Use one increasing 3D scene-save version sequence across all stages in this shot. Do not restart at v001 in each stage. Direct render versions match the producing scene. Preserve earlier saves and outputs. Stage names do not change the filename recipe.

3. Set output paths
In your 3D application, set the render destination to the copied shot’s RENDERS/v001/frames. Set simulations and proxies to its CACHE folder. Verify no output path points back to _SHOT_TEMPLATE.

4. Render and review
Render numbered frames into frames and movies into preview. For a new iteration, save scene v002 and render into a new RENDERS/v002 folder.

5. Composite the shot
Save new comp sources in PROJECTS/COMPOSITING. Existing COMPOSITING/projects saves may remain to preserve dependencies. Set comp outputs to COMPOSITING/renders/v001/frames or preview. Comp versions advance independently.

6. Hand off to the edit
Import the finished composite into the full-video edit. Use direct 3D renders when no comp is required. Client reviews and approved exports go to DELIVERY.

Examples describe your renamed shot, not folders to render into inside the template.

NAMING RECIPE
Project abbreviation (3 letters) + optional version name + shot number (4 digits) + save version (v + 3 digits). Use single underscores. Examples: HVN_Vertical_0010_v001.blend, VRT_Summer_0010_v001.blend, GCR_0010_v001.blend. Shot folders omit the save version: HVN_Vertical_0010. Render frame sequences append a frame number after the base name. Shared assets use the same numbered recipe, for example HVN_Vertical_0010_v001.blend, saved in ASSETS/projects.

PROJECT CODE AND SHOT NUMBERS
Keep the HTML guide at the root of the project folder. When the template is copied into a project-named folder, the guide suggests a 3-letter project abbreviation from that folder name. Review and edit the suggestion if needed. Template folders do not generate a project code. Shots start at 0010 and advance by 10: 0020, 0030, and so on.
