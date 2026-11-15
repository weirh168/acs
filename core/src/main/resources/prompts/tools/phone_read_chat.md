Read a long list or chat by scrolling and collecting the text, instead of observing screen after screen.

It reads the current screen with on-device OCR, scrolls down, reads again, and keeps only lines it has not seen before. `region` limits reading to one area (`left,top,right,bottom` in 0-999) on every screen — good for a chat column when the page also has sidebars or ads. It stops when a screen adds nothing new or after `maxScreens` screens (default 5, up to 20).

Use it for chat history, long article bodies, notification lists, order lists: the result is one de-duplicated list of lines in reading order plus `screens` (how many were read) and `truncated` (stopped early with more content left).

It only scrolls down and only reads text; it does not tap, open items, or go back. For a target you already know, `phone_find` or `phone_query` is cheaper. For a single screen, `phone_observe` is enough.
