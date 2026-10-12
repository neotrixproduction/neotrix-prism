# Start using Neotrix Prism

1. Extract the Windows ZIP into a stable local folder.
2. Double-click **Launch Neotrix Prism.cmd**. Python and Qt are bundled.
3. Open Settings and check your storage roots and application executables.
4. Open Projects, choose a project and double-click a working file.

Projects use equal-size cards with equal spacing. Click a card or press Enter.
Choose a named campaign version when present (such as Vertical or Summer), then
choose a production stage. General contains files without a named version.
Save revisions such as v001 remain visible in the final file list.

File rows support Ctrl/Shift multi-selection. Double-click or Enter opens the
current file. Use Assign stage to label selected files. Breadcrumb links return
to versions, stages or the project library. Scrollbars stay hidden; wheel,
keyboard and touchpad scrolling remain available.

## Project icons and shared stages

Put `project.png`, `project.svg` or `project.webp` in each project's `_TOOLS/icon`.
PNG takes precedence. Missing or corrupt artwork falls back to the template
placeholder, then the bundled placeholder. Icons load in the background and
remain cached offline; Refresh updates them. The template placeholder lives at
`N:\Projects\Template\COMMERCIAL_ADS_TEMPLATE_V3\_TOOLS\icon\project.png`.

Modelling is inferred from `3D/ASSETS/projects`; Compositing from shot
`COMPOSITING/projects`. Shot `PROJECTS` files begin as Unassigned because the
same folder contains layout and lighting scenes. Assign those stages explicitly.
Other work keeps graphics, motion graphics and legacy files accessible.

Stage assignments are shared in `_TOOLS/neotrix-prism/stages.json`, using paths
relative to the project. Files stay in their existing folders. Concurrent edits
are rejected with instructions to refresh. Labels remain viewable from cache
offline, but editing requires a connected writable project. A successful new
version inherits its source document's explicit stage; old revisions retain theirs.

Manrope is bundled. Labels render without perspective transforms; depth and
hover effects apply to artwork. Reduce Motion disables animated transitions.

The default library is Relay. Existing project folders are scanned in place.
No migration is performed. Refresh with F5; scans can be cancelled. Storage
errors are surfaced, and cached project files remain viewable offline.

## Creative application integrations

Run **Install Integrations.cmd** from the extracted package. Keep the package in
that location after installing integrations because their configuration points
to its runtime.

- **Blender 5.2:** enable Neotrix Prism in Preferences > Add-ons. The Neotrix
  sidebar has Explore Projects, Save New Version and Production Tools.
- **After Effects:** restart AE; open Window > Extensions > Neotrix Prism. The
  installer enables local unsigned CEP extensions for the current Windows user.
- **Photoshop 2026:** the installer attempts CCX installation through Creative
  Cloud's UPI. Open Plugins > Neotrix Prism after installation. If UPI is absent,
  use File > Scripts > Browse and select the generated Neotrix Prism.jsx in
  integration-packages/photoshop. This opens the same Qt workspace through the
  native Photoshop adapter. The docked UXP panel needs Creative Cloud or the UXP
  Developer Tool; this preview does not install those applications.

The desktop workspace must be running for Adobe panel commands. The AE panel
starts it if necessary. Ports 16400 and 19888 are used on localhost; standard
Prism's integration identifiers and ports are left separate.

Save New Version saves the active application's current document, including
unsaved edits. It previews the next filename and never replaces a previous
version. If another artist saved a version after the preview, preview again.
If saving from a selected desktop file, that same file must be active in the
application. Illustrator and Fusion version saving is outside this preview.

## Maintenance

Local settings and history are under LocalAppData/NeotrixPrism. Include project `_TOOLS/neotrix-prism` metadata and managed projects'
00_Pipeline configuration in your backup. Existing graph documents are retained
but Workflows is no longer available in the desktop or portable package.

Version reservations and stage edits use exclusive .lock files. If a process
crashes, verify that no save/edit is active before manually removing its stale
lock. Locks are never expired automatically while another save may be running.

Upstream updates are deliberately merged and tested; this fork does not use
Prism Hub to replace itself. See UPSTREAM.md and VALIDATION.md.
