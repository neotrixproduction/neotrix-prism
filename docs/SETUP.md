# Start using Neotrix Prism

1. Extract the Windows ZIP into a stable local folder.
2. Double-click **Launch Neotrix Prism.cmd**. Python and Qt are bundled.
3. Open Settings and check your storage roots and application executables.
4. Open Projects, choose a project and double-click a working file.

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

## Workflows

The shared library is _NEOTRIX_PRISM/Graphs under the configured workflow root.
An example graph is shipped under examples/. Import it and save it to the shared
library, or open the example already installed on Relay.

Choose a project context. Drag matching ports to connect nodes; double-click a
node to edit its properties. Scroll to zoom, middle-drag to pan, and Delete to
remove selected nodes. Arrow keys move a focused node; Enter opens its inspector.

Build Destination Path uses a relative folder inside the selected project.
Preview shows planned copies, folders and launches. Run is manual. Copies keep
their relative directory structure and skip existing destinations. Cancellation
keeps completed copies in the Activity report and removes an incomplete copy
created by that run. Errors stop subsequent actions.

Graph documents have format version 1, a revision number, typed nodes and edges.
No arbitrary scripts, commands, deletes, moves or background triggers are
available. Reconnect the shared library before editing or running cached graphs.

## Maintenance

Local settings and history are under LocalAppData/NeotrixPrism. Include the shared
graph directory and managed projects' 00_Pipeline configuration in your backup.

Version reservations and graph edits use exclusive .lock files. If a process
crashes, verify that no save/edit is active before manually removing its stale
lock. Locks are never expired automatically while another save may be running.

Upstream updates are deliberately merged and tested; this fork does not use
Prism Hub to replace itself. See UPSTREAM.md and VALIDATION.md.
