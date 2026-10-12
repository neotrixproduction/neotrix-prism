# Neotrix Prism

A Windows creative-project workspace built on the open-source Prism Pipeline.
Browse existing project folders across Blender, Illustrator, Photoshop, After
Effects and Fusion, save working versions, and connect reusable file workflows.

The interface uses original Neotrix artwork, rounded tiles, colorful icons and
lightweight motion inspired by the current CleanMyMac design.

![Neotrix workspace](docs/screenshots/home.png)
![Working files across applications](docs/screenshots/projects.png)
![Independent file-workflow editor](docs/screenshots/workflows.png)

## Run on Windows

Download the Windows preview package from this repository's Releases, extract it
to a stable folder, and double-click **Launch Neotrix Prism.cmd**. Python and Qt
are included; there is no separate Python installation.

Open Settings to check storage roots and application paths. Relay is the default
shared project library. Projects are scanned in place; existing production
folders are not migrated or renamed.

Run **Install Integrations.cmd** for the separate Blender and Adobe integrations.
Photoshop's docked UXP panel requires Adobe's UXP installer; a companion JSX can
open the Qt workspace when that installer is unavailable.

See [Setup](docs/SETUP.md) for opening files, version saving and shared workflows.

## Included

- Project cards/list views, search, favorites and recent projects.
- Application, department, variant, shot, stage and version filters.
- Working-file and output views, existing image previews and application icons.
- Open, Open With, Reveal Folder and Copy Path actions.
- In-memory version saves through Blender, Photoshop and After Effects adapters.
- An independently implemented typed graph editor: find, filter, build paths,
  create folders, copy, open and log. Runs are manual and previewed.
- Shared JSON workflows, edit-conflict detection, offline caches and local history.
- Light/dark appearance, keyboard focus and a reduced-motion setting.
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

Our graph editor does not use the official commercial Execution Graph.
Automatic upstream replacement is disabled; upgrades are merged and tested.

- [Development](docs/DEVELOPMENT.md)
- [Upstream changes](UPSTREAM.md)
- [Original upstream README](docs/UPSTREAM_README.md)

Neotrix additions are LGPL-3.0-or-later. Existing components retain their
applicable upstream licenses. Runtime third-party licenses are in the Windows
package. User preferences, real production files and credentials are excluded
from this repository.