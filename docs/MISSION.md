# Neotrix Prism — Mission and purpose

## Mission

Give Neotrix artists one clear, beautiful Windows workspace to find the right
project, choose the right working file, and continue creating with confidence.

Neotrix Prism brings the studio's existing production folders and creative
applications together through visual project browsing, meaningful stage labels,
and safe working-file versioning.

## Who it is for

Neotrix artists, designers, animators and compositors working across Blender,
Photoshop, Illustrator, After Effects and standalone Fusion. It also helps team
members understand where project work belongs and pick up shared production work.

The desktop explorer runs on Windows. Artists can browse before opening a creative
application, and supported application integrations connect document-saving
actions to the same workspace.

## What the app is for

- **Find projects visually.** Browse project cards with recognizable artwork,
  search the studio library, and keep frequently used projects or files in Favorites.
- **Choose the right context.** Open a project and choose Versions (Working files
  when no named versions exist), Assets or Preview. Working files follow named
  version → production stage → file list; Assets and Preview open their own lists,
  with breadcrumbs and back navigation.
- **Open creative work.** See the application, filename, shot, saved revision,
  modification date and path, then open the file or reveal its folder.
- **Save the next working revision safely.** Through supported adapters, save
  the active document, including unsaved edits, into its current working directory
  using the next available version name, with overwrite protection.
- **Share meaningful stage labels.** Explicitly assign Layout, Lighting and other
  stages where folders cannot distinguish them. Store labels as shared project
  metadata while preserving production files and their locations.
- **Stay oriented.** Refresh the library, browse cached information when storage
  is unavailable, and review local activity. Keep application paths, storage roots
  and Prism production tools in Settings.

Named versions such as **Vertical** or **Summer** describe a campaign or delivery
variant. Save revisions such as **v001** and **v002** describe successive working
files. The interface must keep this distinction clear.

## Product principles

### Respect the studio's existing work

Browse existing production folders in place. Preserve names, structure and custom
project artwork. Keep legacy-folder browsing distinct from Prism-managed projects.
Shared labels and version reservations should support collaboration without
silently replacing another artist's work.

### Make creative work easy to recognize

Use large, colorful, image-generated 3D artwork for projects, versions and stages.
Use quieter monochrome navigation icons. Keep copy brief and show useful detail
when an artist needs it.

### Make the interface feel polished

Follow the accepted CleanMyMac-inspired direction with Neotrix identity: dark
colored backgrounds, brighter glass-like panels, rounded surfaces, Manrope,
consistent spacing and responsive motion. Refresh should feel satisfying on every
page. Artwork can move; text must remain crisp and legible. Support reduced motion.

### Keep production actions predictable

Make destinations and proposed version names visible before saving. Report storage,
application and concurrency errors clearly. Keep long scans cancellable and keep
the interface responsive.

## Scope boundaries

The product focuses on project browsing, creative-file access, stage organization
and working versions. The independent Workflows feature and Home page have been
removed. Projects is the opening page; native Prism production tools remain
available through Settings.

Blender, Photoshop and After Effects are the intended application-aware version-save
integrations. Illustrator and standalone Fusion initially support browsing and
opening. Resolve database projects are a separate concern.

## Foundation and delivery

Neotrix Prism is a customized open-source Prism Pipeline fork. Reuse Prism's Qt
framework, adapters and pipeline services while retaining upstream attribution
and applicable licenses. Keep Neotrix preferences and integrations separate from
standard Prism. Deliver a portable Windows application with its own runtime.

This document describes product intent and scope, not proof that every workflow
has passed final validation. The current UI is being iterated in source; final
testing and package rebuilds wait until the user says **done**.

## What success looks like

An artist can quickly identify a project, select its variant and stage, open the
correct file, and save a new revision confidently. The experience is visually
coherent, responsive and comfortable across Neotrix's creative applications and
shared storage.
