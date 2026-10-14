# Relay V3 folder reference

Extracted from the bundled interactive V3 guide. Paths are project-relative.

| Folder | Purpose |
| --- | --- |
| `01_ADMIN` | Business documents and project coordination. |
| `01_ADMIN/agreements` | Signed contracts and scope agreements. |
| `01_ADMIN/quotes_and_invoices` | Commercial estimates and billing. |
| `01_ADMIN/correspondence` | Official decisions and communication records. |
| `01_ADMIN/schedule` | Milestones, timelines, and team availability. |
| `02_PREPRODUCTION` | Creative planning and the authoritative production brief. |
| `02_PREPRODUCTION/brief` | The authoritative creative brief; keep revisions here. |
| `02_PREPRODUCTION/script` | Scripts and approved wording. |
| `02_PREPRODUCTION/references` | Visual and technical inspiration. |
| `02_PREPRODUCTION/moodboards` | Visual direction and look exploration. |
| `02_PREPRODUCTION/storyboards` | Framing and action across the commercial. |
| `02_PREPRODUCTION/shot_list` | Shot IDs, descriptions, timing, and status. |
| `02_PREPRODUCTION/asset_list` | Required models, graphics, and other assets. |
| `02_PREPRODUCTION/approvals` | Records of approved creative decisions. |
| `03_PRODUCTION` | Source materials and active content creation. |
| `03_PRODUCTION/INPUT` | Received originals. Never overwrite original materials. |
| `03_PRODUCTION/INPUT/CLIENT_ASSETS` | Original materials supplied by the client. |
| `03_PRODUCTION/INPUT/CLIENT_ASSETS/brand_guidelines` | Client brand rules. |
| `03_PRODUCTION/INPUT/CLIENT_ASSETS/fonts` | Supplied font files and license information. |
| `03_PRODUCTION/INPUT/CLIENT_ASSETS/logos` | Original client logo artwork. |
| `03_PRODUCTION/INPUT/CLIENT_ASSETS/packaging` | Original product packaging artwork. |
| `03_PRODUCTION/INPUT/CLIENT_ASSETS/product_photos` | Supplied product photography. |
| `03_PRODUCTION/INPUT/CLIENT_ASSETS/music` | Original client-supplied music. |
| `03_PRODUCTION/INPUT/CLIENT_ASSETS/video_references` | Client-supplied reference films. |
| `03_PRODUCTION/INPUT/CAPTURED_MEDIA` | Untouched recordings and capture data. |
| `03_PRODUCTION/INPUT/CAPTURED_MEDIA/footage` | Original camera footage. |
| `03_PRODUCTION/INPUT/CAPTURED_MEDIA/audio` | Original location sound and recorded voice. |
| `03_PRODUCTION/INPUT/CAPTURED_MEDIA/mocap` | Original motion capture recordings. |
| `03_PRODUCTION/INPUT/CAPTURED_MEDIA/scans` | Original scan data. |
| `03_PRODUCTION/WORK` | Editable projects and generated production material. |
| `03_PRODUCTION/WORK/3D` | CG asset development and shot production. |
| `03_PRODUCTION/WORK/3D/ASSETS` | Reusable assets shared across shots. |
| `03_PRODUCTION/WORK/3D/ASSETS/projects` | Asset modeling and look-development project saves. |
| `03_PRODUCTION/WORK/3D/ASSETS/models` | Reusable model files used by scenes. |
| `03_PRODUCTION/WORK/3D/ASSETS/textures` | Shared texture maps and image resources. |
| `03_PRODUCTION/WORK/3D/ASSETS/exports` | Shared asset interchange exports. |
| `03_PRODUCTION/WORK/3D/SHOTS` | One folder per shot. Copy _SHOT_TEMPLATE manually and rename the copy. |
| `03_PRODUCTION/WORK/3D/SHOTS/_SHOT_TEMPLATE` | Copy this folder for each new shot. Do not save production work in the template. |
| `03_PRODUCTION/WORK/3D/SHOTS/_SHOT_TEMPLATE/PROJECTS` | Editable shot projects organized by production stage. Existing unclassified saves may remain directly here. |
| `03_PRODUCTION/WORK/3D/SHOTS/_SHOT_TEMPLATE/PROJECTS/MODELLING` | Shot-specific modelling and geometry work. Reusable models belong in 3D/ASSETS. |
| `03_PRODUCTION/WORK/3D/SHOTS/_SHOT_TEMPLATE/PROJECTS/RIGGING` | Shot-specific rigs, controls, and deformation setup. |
| `03_PRODUCTION/WORK/3D/SHOTS/_SHOT_TEMPLATE/PROJECTS/LAYOUT` | Shot cameras, composition, staging, and rough timing. |
| `03_PRODUCTION/WORK/3D/SHOTS/_SHOT_TEMPLATE/PROJECTS/ANIMATION` | Shot character, object, and camera animation. |
| `03_PRODUCTION/WORK/3D/SHOTS/_SHOT_TEMPLATE/PROJECTS/FX` | Editable shot simulation and effects setups. Generated caches belong in the shot CACHE folder. |
| `03_PRODUCTION/WORK/3D/SHOTS/_SHOT_TEMPLATE/PROJECTS/LIGHTING` | Shot lighting, materials, look development, and render setup. |
| `03_PRODUCTION/WORK/3D/SHOTS/_SHOT_TEMPLATE/PROJECTS/COMPOSITING` | Editable shot composites combining renders, footage, and effects. |
| `03_PRODUCTION/WORK/3D/SHOTS/_SHOT_TEMPLATE/PROJECTS/OTHERS` | Other editable shot work that does not fit a named stage. |
| `03_PRODUCTION/WORK/3D/SHOTS/_SHOT_TEMPLATE/RENDERS` | Direct output from the 3D renderer. |
| `03_PRODUCTION/WORK/3D/SHOTS/_SHOT_TEMPLATE/RENDERS/v001` | First render version. Create v002 and later versions as needed. |
| `03_PRODUCTION/WORK/3D/SHOTS/_SHOT_TEMPLATE/RENDERS/v001/frames` | Rendered image sequences. Keep passes within this output, as multilayer files or pass subfolders. |
| `03_PRODUCTION/WORK/3D/SHOTS/_SHOT_TEMPLATE/RENDERS/v001/preview` | Rendered movies and internal review encodes. |
| `03_PRODUCTION/WORK/3D/SHOTS/_SHOT_TEMPLATE/COMPOSITING` | Shot-level assembly of 3D passes, footage, and visual effects. |
| `03_PRODUCTION/WORK/3D/SHOTS/_SHOT_TEMPLATE/COMPOSITING/projects` | Legacy compositing source folder. Save new comp projects in PROJECTS/COMPOSITING; preserve existing linked work here. |
| `03_PRODUCTION/WORK/3D/SHOTS/_SHOT_TEMPLATE/COMPOSITING/renders` | Finished shot composites to feed the edit. |
| `03_PRODUCTION/WORK/3D/SHOTS/_SHOT_TEMPLATE/COMPOSITING/renders/v001` | First render version. Create v002 and later versions as needed. |
| `03_PRODUCTION/WORK/3D/SHOTS/_SHOT_TEMPLATE/COMPOSITING/renders/v001/frames` | Rendered image sequences. Keep passes within this output, as multilayer files or pass subfolders. |
| `03_PRODUCTION/WORK/3D/SHOTS/_SHOT_TEMPLATE/COMPOSITING/renders/v001/preview` | Rendered movies and internal review encodes. |
| `03_PRODUCTION/WORK/3D/SHOTS/_SHOT_TEMPLATE/CACHE` | Shot-specific simulations, geometry caches, and proxies. |
| `03_PRODUCTION/WORK/3D/SHOTS/_SHOT_TEMPLATE/EXPORTS` | Shot-specific interchange exports for another tool. |
| `03_PRODUCTION/WORK/MOTION_GRAPHICS` | Motion design, titles, and standalone animated graphics. |
| `03_PRODUCTION/WORK/MOTION_GRAPHICS/projects` | Editable motion design projects. |
| `03_PRODUCTION/WORK/MOTION_GRAPHICS/assets` | Working graphics and resources used by motion design. |
| `03_PRODUCTION/WORK/MOTION_GRAPHICS/renders` | Rendered motion graphics for the edit. |
| `03_PRODUCTION/WORK/GRAPHIC_DESIGN` | Static visuals and editable artwork. |
| `03_PRODUCTION/WORK/GRAPHIC_DESIGN/projects` | Editable design source files. |
| `03_PRODUCTION/WORK/GRAPHIC_DESIGN/assets` | Working design resources and editable derivatives. |
| `03_PRODUCTION/WORK/GRAPHIC_DESIGN/exports` | Exported graphics for production. |
| `03_PRODUCTION/WORK/AI_GENERATION` | AI-generated production material with reproducible settings. |
| `03_PRODUCTION/WORK/AI_GENERATION/inputs` | Working inputs supplied to generation tools. |
| `03_PRODUCTION/WORK/AI_GENERATION/workflows` | Prompts, workflows, and generation settings. |
| `03_PRODUCTION/WORK/AI_GENERATION/outputs` | Generated output batches; keep associated prompts/settings identifiable. |
| `04_POST` | Full-video assembly, conform, color, and sound finishing. |
| `04_POST/EDIT` | Editorial assembly of the full video. |
| `04_POST/EDIT/projects` | Timeline and editing project saves. |
| `04_POST/EDIT/exports` | Internal edit exports and handoffs. |
| `04_POST/FINISHING` | Final assembly and conform to high-quality sources. |
| `04_POST/FINISHING/projects` | Finishing and master timeline projects. |
| `04_POST/FINISHING/conform` | Timeline interchange files and relink information. |
| `04_POST/COLOR` | Color grading work and look references. |
| `04_POST/COLOR/projects` | Grading projects. |
| `04_POST/COLOR/luts` | Color lookup tables. |
| `04_POST/COLOR/stills` | Grading reference frames; add preview subfolders if needed. |
| `04_POST/AUDIO` | Sound editing, music, effects, and mixing. |
| `04_POST/AUDIO/projects` | Editable sound sessions. |
| `04_POST/AUDIO/voice` | Working voice recordings and edits. |
| `04_POST/AUDIO/music` | Working music tracks. |
| `04_POST/AUDIO/sfx` | Sound effect resources. |
| `04_POST/AUDIO/mixes` | Rendered audio mixes and stems. |
| `05_DELIVERY` | Client-facing review exports and final approved deliverables only. |
| `05_DELIVERY/REVIEW` | Client review exports, grouped by version. |
| `05_DELIVERY/REVIEW/v001` | First client review package; create new versions as needed. |
| `05_DELIVERY/FINAL` | Approved masters and cutdowns. Create only required duration, aspect ratio, and version folders. |
| `_TOOLS` | Reusable production setup files, not shot content. |
| `_TOOLS/scene_templates` | Starter scenes for your applications. |
| `_TOOLS/render_presets` | Reusable render settings. |
| `_TOOLS/icon` | Project artwork. `project.png` is the bundled placeholder. |
