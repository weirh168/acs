Read a long list or chat by scrolling and collecting the text, instead of observing screen after screen.

It reads the current screen with on-device OCR, scrolls, reads again, and keeps only lines it has not seen before. `region` limits reading to one area (`left,top,right,bottom` in 0-999) on every screen — good for a chat column when the page also has sidebars or ads. It stops when a screen adds nothing new or after `maxScreens` screens (default 5, up to 20).

`direction` decides which way it moves. The default `down` reads newer content below (an article body, an order list). Use `up` to read older content above — that is the normal case for chat history and notification lists, which are always anchored at the newest item: the chat opens at the bottom, and scrolling up is how you reach yesterday. The returned `lines` are always in reading order regardless of direction (for `up`, the screens are stitched in reverse so the oldest line comes first), and `direction` echoes what was used.

`settleMs` (100-3000, default 500) is how long to wait after each scroll before reading again. Raise it on a slow device or when the list animates: reading too early returns the previous screen and the tool stops early with `truncated: true`.

Use it for chat history, long article bodies, notification lists, order lists: the result is one de-duplicated list of lines in reading order plus `screens` (how many were read) and `truncated` (stopped early with more content left).

It only scrolls and only reads text; it does not tap, open items, or go back. For a target you already know, `phone_find` or `phone_query` is cheaper. For a single screen, `phone_observe` is enough.
`until` is the other way to decide where to stop: pass a piece of text and the tool stops as soon as a line containing it is read, keeping that line and reporting `stoppedBy: "until"`. Read back to the date header you already have, to `以下为新消息`, or to the first message you summarised last time, instead of guessing `maxScreens`. When the marker never shows up it just reads `maxScreens` screens as usual.
`match` filters what comes back without changing how far it reads: it still scrolls, de-duplicates and honours `until`/`maxScreens`, then keeps only the lines containing that text (case-insensitive) and reports `matched` and `dropped`. On a long group chat this is how you pull one sender or one keyword out of thousands of lines without dragging the whole transcript along.

