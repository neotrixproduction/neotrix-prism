# Relay commercial production template V3

A reference snapshot of Neotrix's verified commercial production template,
captured on 2026-10-13. This is the folder convention used by Neotrix Prism's
project browsing, client asset categories, stage inference and video previews.

- [Browse the complete template](COMMERCIAL_ADS_TEMPLATE_V3)
- [Download the template ZIP](COMMERCIAL_ADS_TEMPLATE_V3.zip)
- [Read the folder map on GitHub](FOLDER_MAP.md)
- [Interactive folder guide source](COMMERCIAL_ADS_TEMPLATE_V3/FOLDERING_HELP.html)
- [Snapshot details](SNAPSHOT.json)

GitHub shows HTML source. Download and extract the ZIP, then open
`FOLDERING_HELP.html` in a browser for the interactive guide, filename helper,
glossary and shot walkthrough. Keep the guide at the project root so its relative
folder links resolve. The guide does not create folders or configure applications.

## Start a project

1. Copy the whole `COMMERCIAL_ADS_TEMPLATE_V3` folder to your project library and
   rename the copy to the actual project name. Keep the original as a template.
2. Open the copied `FOLDERING_HELP.html`. Set the project name, accepted
   three-letter code and optional named versions in its project settings.
3. For each shot, copy `03_PRODUCTION/WORK/3D/SHOTS/_SHOT_TEMPLATE` inside `SHOTS`
   and rename the copy, for example `NTX_Vertical_0010`.
4. Save editable documents in the appropriate stage below `PROJECTS`. Configure
   render, cache and linked-file paths in the creative application to point to
   the real shot, rather than `_SHOT_TEMPLATE`.
5. Add the parent project library in Neotrix Prism Settings and refresh Projects.

`.gitkeep` files only preserve empty directories in Git; they can be removed
from a new project. There are no sample Blender/Adobe documents or videos in
this template. Naming examples below are illustrative, not files to open.

## Folder responsibilities

| Root | Contents |
| --- | --- |
| `01_ADMIN` | Agreements, billing, correspondence and schedules. |
| `02_PREPRODUCTION` | Authoritative brief, script, references, storyboards and approvals. |
| `03_PRODUCTION/INPUT` | Untouched client originals and captured media. |
| `03_PRODUCTION/WORK` | Editable 3D, motion graphics, graphic design and AI work. |
| `04_POST` | Full-video editing, finishing, color and audio. |
| `05_DELIVERY` | Client reviews and approved final deliverables. |
| `_TOOLS` | Scene templates, render presets and project artwork. |

## How the app uses this structure

**Assets** presents original client materials from
`03_PRODUCTION/INPUT/CLIENT_ASSETS`: fonts, logos, brand guidelines, packaging,
product photos, music and video references. The authoritative **Brief** stays
in `02_PREPRODUCTION/brief`. Reusable production models and textures belong in
`03_PRODUCTION/WORK/3D/ASSETS` and are separate from client assets.

**Versions / Working files** distinguishes a named campaign version such as
`Vertical` from a save revision such as `v003`. Shot `PROJECTS` folders separate
`MODELLING`, `RIGGING`, `LAYOUT`, `ANIMATION`, `FX`, `LIGHTING`, `COMPOSITING` and
`OTHERS`. Older general saves may remain directly in `PROJECTS`; don't move
linked work merely to match the template. Shared explicit stage labels are
stored by Prism in `_TOOLS/neotrix-prism/stages.json` when needed; that file is
not prepopulated in this template.

**Preview** shows MP4/MOV videos in separate full-video and per-shot collections.
Direct shot previews belong in `RENDERS/vNNN/preview`; finished shot composites
belong in `COMPOSITING/renders/vNNN/preview`. Whole-video internal exports belong
in `04_POST/EDIT/exports`, client feedback videos in `05_DELIVERY/REVIEW/vNNN`,
and approved masters in `05_DELIVERY/FINAL`. EXR sequences belong in `frames`.

## Concrete naming examples

`NTX` is a fictional example project code; use your actual accepted code.
Shot IDs advance in increments of ten: `0010`, `0020`, `0030`.
Optional named versions use letters and digits without spaces or punctuation.

| Role | Example project-relative path |
| --- | --- |
| Client logo original | `03_PRODUCTION/INPUT/CLIENT_ASSETS/logos/client_logo.ai` |
| Creative brief | `02_PREPRODUCTION/brief/creative_brief_v001.pdf` |
| Shared Blender asset source | `03_PRODUCTION/WORK/3D/ASSETS/projects/NTX_Vertical_0010_v001.blend` |
| Shot layout | `03_PRODUCTION/WORK/3D/SHOTS/NTX_Vertical_0010/PROJECTS/LAYOUT/NTX_Vertical_0010_v001.blend` |
| Later shot lighting save | `03_PRODUCTION/WORK/3D/SHOTS/NTX_Vertical_0010/PROJECTS/LIGHTING/NTX_Vertical_0010_v003.blend` |
| Direct render frame | `03_PRODUCTION/WORK/3D/SHOTS/NTX_Vertical_0010/RENDERS/v003/frames/NTX_Vertical_0010_v003_0001.exr` |
| Internal shot video | `03_PRODUCTION/WORK/3D/SHOTS/NTX_Vertical_0010/RENDERS/v003/preview/NTX_Vertical_0010_v003.mp4` |
| Shot composite source | `03_PRODUCTION/WORK/3D/SHOTS/NTX_Vertical_0010/PROJECTS/COMPOSITING/NTX_Vertical_0010_v001.aep` |
| Finished shot composite | `03_PRODUCTION/WORK/3D/SHOTS/NTX_Vertical_0010/COMPOSITING/renders/v001/preview/NTX_Vertical_0010_v001.mov` |
| Whole-video client review | `05_DELIVERY/REVIEW/v002/NTX_Vertical_v002.mp4` |

Use one increasing 3D scene-save revision sequence across a shot's 3D stages;
don't restart at `v001` in each stage. Match direct render revisions to the
producing scene. Compositing revisions advance independently. Keep previous
saves and outputs, and never overwrite received originals.

## Project artwork and provenance

`_TOOLS/icon/project.png` is the template's original generated placeholder.
Replace it with artwork for a new project; preserve existing project artwork.
Prism also accepts `project.svg` and `project.webp` alternatives.

The bundled guide and placeholder are unchanged from the live template.
Folder instructions are retained; only the root README's outdated guide filename
was corrected. The snapshot contains no client production content, personal
preferences, credentials or workstation configuration. The guide includes its
embedded font license notices. This example does not modify the live template
and does not change the app's UI or animations.
