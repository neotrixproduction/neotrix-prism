# Neotrix Prism

A Windows creative-project workspace built on the open-source Prism Pipeline.
Browse existing project folders across Blender, Illustrator, Photoshop, After
Effects and Fusion, save working versions, and organize files with shared stage labels.

The interface uses a continuous purple-to-indigo background, luminous tinted
tiles, dimensional original icons and choreographed motion inspired by the current
CleanMyMac design. Dark mode is the only appearance. Sidebar, file lists, settings and native Prism dialogs share
the same visual system. Opening a project shows **Assets | Versions/Working files | Preview**.
Client assets have category cards; working files follow named-version and stage choices;
previews separate full-video and per-shot MP4/MOV outputs. Scroll, drag or use arrow
keys to browse. Scrollbars are hidden across Neotrix surfaces.

The rounded Windows shell includes custom window controls, draggable caption,
edge resizing and a collapsible animated sidebar. Projects is the opening page.
Retargetable springs, artwork-derived colors, floating 3D artwork, zoom-through
navigation and a refresh shockwave share the same motion system. The glass Refresh
control follows workspace colors and becomes Stop during real tasks. Reduced motion
settles active transitions. Native-size labels remain separate from artwork transforms.

Manrope provides heading and body typography with distinct sizes and weights.
The OFL font files and license are bundled; no font installation is required.
See [Motion and visual reference](docs/MOTION.md).

Creative applications use thick 3D artwork based on their actual installed app
icons. The transparent assets and complete generation prompts are in
[assets/app-icons](assets/app-icons/SOURCE.json). These are rendered PNG assets,
not mesh models. Existing preview images are used without launching applications.

[Watch the real Qt motion preview](docs/screenshots/motion.mp4).

The screenshots and recorded motion below show earlier preview revisions.
![Working files across applications](docs/screenshots/projects.png)
![Uniform project grid](docs/screenshots/project-library.png)
![Production stage cards](docs/screenshots/stages.png)

## Run on Windows

Download the Windows preview package from this repository's Releases, extract it
to a stable folder, and double-click **Neotrix Prism.exe**. Python and Qt
are included; there is no separate Python installation.

Open Settings to check storage roots and application paths. Relay is the default
shared project library. Projects are scanned in place; existing production
folders are not migrated or renamed.

Optionally run **Create Desktop Shortcut.cmd** for the app shortcut.
Run **Install Integrations.cmd** for the separate Blender and Adobe integrations.
Photoshop's docked UXP panel requires Adobe's UXP installer; a companion JSX can
open the Qt workspace when that installer is unavailable.

See [Start here](START_HERE.md) for another PC and [Setup](docs/SETUP.md) for project
icons, stage labels, opening files and version saving.

## Included

- Uniform project cards, named campaign versions, 3D stage cards and a multi-selection file list.
- Per-project artwork loaded asynchronously from `_TOOLS/icon`, with cached fallback.
- Shared stage labels with concurrent-edit protection and offline browsing.
- Application, shot and save-revision filters; working files and outputs.
- Open, Open With, Reveal Folder, Copy Path, favorites and recent projects.
- In-memory version saves through Blender, Photoshop and After Effects adapters.
- Dark appearance, keyboard focus and a reduced-motion setting.
- Retained Prism-managed project and production services with the Neotrix theme.

The screenshots use fictional indexing fixtures. They are screenshots of the
native Qt app, not browser mockups.

## Preview status

Real open/save/reopen checks passed for Blender, Photoshop and After Effects;
file-opening checks passed for Illustrator and Fusion. Desktop scaling was
reviewed at 100%, 150% and 200%.

The Photoshop UXP installation and the true two-workstation pilot are still
pending. Native advanced Prism tools keep their established layouts with the
shared Neotrix theme. See [Validation](VALIDATION.md) for evidence and limits.

## Source and maintenance

Forked from [PrismPipeline/Prism](https://github.com/PrismPipeline/Prism), pinned to
v2.1.3, fd440de6747b7e62e2ba8cb675028e7adbbce1e3. Upstream history and license notices
are retained. No commercial Prism plugins are included.

The independent Workflows feature is removed from this release. Existing shared graph documents are preserved.
Automatic upstream replacement is disabled; upgrades are merged and tested.

- [Development](docs/DEVELOPMENT.md)
- [Upstream changes](UPSTREAM.md)
- [Original upstream README](docs/UPSTREAM_README.md)

Neotrix additions are LGPL-3.0-or-later. Existing components retain their
applicable upstream licenses. Runtime third-party licenses are in the Windows
package. User preferences, real production files and credentials are excluded
from this repository.
