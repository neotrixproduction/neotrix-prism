# Neotrix motion and rounded window

The current design was compared with MacPaw's official
[CleanMyMac overview](https://macpaw.com/cleanmymac) and its
[30-second interface demo](https://cdn3.macpaw.com/video/cleanmymac5-overview/en-cleanmymac5-overview.mp4).
Three focused reference checks covered the introduction/sidebar change, active
tile emphasis and task progress, and the completed tile grid/window silhouette.

Neotrix follows the visible patterns with its own creative-project artwork.
Exact proprietary easing curves and internal timing are not available from the
public demo. The following are our implementation values, not measurements of
CleanMyMac's source animation system.

| Interaction | Motion |
| --- | --- |
| Page and file details | 340 ms fade with 22 px vertical reveal |
| Navigation selection | 320 ms continuous highlight slide |
| Sidebar collapse/expand | 380 ms width transition, tooltips retained |
| Tile focus | 350–450 ms bloom and up to 12% layout emphasis |
| Dimensional icons | 600 ms spring entrance, 75 ms stagger; 480 ms hover lift/rotation |
| Buttons | 220–260 ms hover; 140 ms press and 280 ms spring release |
| Graph nodes | 220–300 ms hover outline/glow |
| Circular action | Hover/press scaling; task ring rotates only during a real worker |
| Adobe panels | Staggered entrance, card lift, button press and icon tilt |

Finite timelines stop at rest. Task rotation stops after completion/cancellation,
when hidden/minimized, or when reduced motion is enabled. File rows do not have
independent continuous effects. Native host panel CSS support still requires
the host validation noted in VALIDATION.md.

The desktop window has 26 px corners, a restrained painted shadow, a custom
caption and accessible close/minimize/maximize controls. It supports caption
dragging, edge resizing with the 1024 x 720 minimum, and maximize/restore. Windows
maximized mode uses square corners and removes the outer margin.

Typography uses bundled **Manrope** for headings, body and controls, with
different sizes and weights. It comes from
[Google Fonts](https://github.com/google/fonts/tree/main/ofl/manrope); the
unmodified font and SIL OFL license are in assets/fonts.

For separately licensed local fonts, developers can set NEOTRIX_FONT_DIR,
NEOTRIX_FONT_DISPLAY and NEOTRIX_FONT_TEXT. These are local overrides; custom
font files are never added to a package by that mechanism.
