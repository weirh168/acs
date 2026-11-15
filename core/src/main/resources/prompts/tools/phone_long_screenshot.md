Take one tall screenshot by scrolling and stitching, without repeating or losing content.

`direction` is `vertical` (default, scrolls down) or `horizontal` for wide content that scrolls sideways: wide tables, code, timelines. Frames are aligned by matching rows that are unique on both sides, so seams join correctly; `overlaps` reports how far each screen actually scrolled.

`maxScreens` caps how many frames are taken (default 6, at most 12). It stops early when the content stops changing.

`savePath` keeps the PNG under /workspace so you can hand it to the user with share_file; models that can view images get it directly when savePath is omitted. Very long pages are split into `<name>-1.png`, `<name>-2.png` … (each a full image, 8000 px tall at most); then savePath is required.

If a popup, dim overlay or page jump interrupts the scroll, the result carries `blocked` plus a hint and the screen is left untouched: observe it, deal with whatever is in the way, then call again.

Reading text is cheaper with `phone_read_chat`; this tool is for when the layout itself matters.
`startFrom` positions the page before shooting: `top` scrolls up until the list stops moving, `bottom` scrolls down the same way, `current` (default) shoots where it is. A list someone left half-way down therefore still comes out complete. The result says how many pre-scrolls it took (`preScrolls`) and whether it really hit the edge (`atEdge`).

`settleMs` (0-3000, default 400) is the pause between positioning and the first frame; raise it on slow pages or when the list animates.

