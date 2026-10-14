# Upstream and maintenance

Neotrix Prism is a fork of PrismPipeline/Prism, pinned to v2.1.3,
fd440de6747b7e62e2ba8cb675028e7adbbce1e3.

The desktop workspace, original icon artwork, workflow graph, storage/indexing
services and application wrappers live in neotrix_prism/. The Blender add-on
and Adobe panels have separate Neotrix identifiers.

Upstream changes:

- The After Effects adapter accepts NEOTRIX_AE_PORT; its default stays unchanged.
- The Photoshop adapter does not start the upstream HTTP bridge in a Neotrix
  session. Neotrix's bridge uses a separate port and a command whitelist.

The upstream application adapters still save the active in-memory document.
Existing file saves are routed through our version reservation service. Native
managed-project services remain upstream Prism services.

No commercial Prism plugins are included. Our file graph is independently
authored and does not use the commercial Execution Graph plugin.

Preserve all upstream license notices. Neotrix modules are LGPL-3.0-or-later.
Existing upstream component licenses retain their original terms.

Use a maintenance branch to merge upstream changes. Review the two adapter
changes, run tests, rebuild runtime packages and visually inspect desktop and
application interfaces before release. The Neotrix launcher excludes Hub and
PrismInternals from automatic loading.
