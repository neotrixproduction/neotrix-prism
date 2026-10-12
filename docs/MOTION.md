# Neotrix motion and rounded window

The current design was compared with MacPaw's official
[CleanMyMac overview](https://macpaw.com/cleanmymac) and its
[30-second interface demo](https://cdn3.macpaw.com/video/cleanmymac5-overview/en-cleanmymac5-overview.mp4).
Reference checks covered the introduction/sidebar change, active tile expansion,
task progress, and the completed tile grid/window silhouette. The 0.3 revision
also researched Apple's [Meet Liquid Glass](https://developer.apple.com/videos/play/wwdc2025/219/)
for fluid continuity and reactive highlights, and the original CleanMyMac
[3D campaign case study](https://www.and-action.net/projects/cleanmymac) for dimensional
art direction. The campaign is a film reference, not evidence of native UI behavior.

Neotrix follows the visible patterns with its own creative-project artwork.
Exact proprietary easing curves and internal timing are not available from the
public demo. The following are our implementation values, not measurements of
CleanMyMac's source animation system.

| Interaction | Motion |
| --- | --- |
| Tile-to-page navigation | 420 ms growing rounded mask, full-size crisp content |
| Sidebar page navigation | 420 ms directional depth transition; outgoing snapshot retreats |
| Card and file details entrance | 340 ms opacity, 54 px travel and scale settlement; cards stagger 65 ms |
| Navigation selection | 320 ms continuous highlight slide |
| Sidebar collapse/expand | 380 ms width transition, tooltips retained |
| Tile focus | 520 ms spring expansion, 600 ms return; stretch weight grows up to 65% on larger windows |
| Surface lighting | 180 ms pointer tracking, finite 850 ms sheen sweep; page lighting shifts over 700 ms |
| Dimensional icons | 600 ms spring entrance, 90 ms stagger; larger lift/rotation with pointer parallax and contact shadow |
| Buttons | Hover, press/release spring and finite 580 ms click ripple |
| Graph nodes | 220–300 ms hover outline/glow |
| Circular action | Fixed center across Explore/Stop states; 520 ms state spring, changing arc length and counter-rotating secondary ring during a real worker |
| Adobe panels | Overshoot entrance, perspective card lift, finite highlight sweep, button press and icon tilt |

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
