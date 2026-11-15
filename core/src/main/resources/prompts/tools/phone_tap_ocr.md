Tap a piece of text that is on screen, using on-device OCR instead of the accessibility tree. The line's center is tapped.

Use it when the thing you want is drawn rather than exposed: canvas and game UIs, Flutter/React-Native surfaces, or an item you only saw in `ocrOnly` from phone_observe. When the target has a normal accessibility node, `phone_tap` by ref is still more reliable.

`text` is what you see on screen (the line, or a distinctive part of it). `region` narrows the search to one area, `left,top,right,bottom` in 0-999 coordinates — useful when two lists show the same words and only one of them should be tapped. With `exact: true` the whole line must equal it; by default a line containing it is enough.

Matching lines are ranked, and the first one is tapped: a line equal to `text` beats a longer line that merely contains it, then the shorter line wins (usually the button itself rather than the paragraph around it), then the higher one. When the same text legitimately appears several times — a row of "发送" buttons, a list of identical "编辑" links — pass `index` (0-based, default 0) to pick a later one instead of blindly tapping the first.

The result says which line was matched (`matchedText`, `x`/`y` in 0-999), its 0-based `index` and how many lines matched (`total`; `alsoMatched` is `total - 1`). If nothing matched you get `ocr_no_match` with a few nearby lines: read them and retry with the exact wording, or use phone_observe. If `index` is beyond the matches you get `ocr_index_out_of_range` with the real count: narrow `region` or drop `index`.
`waitMs` handles the screen still moving: with `waitMs: 1500` the tool re-reads the screen every 250ms until something matches or the time runs out, so a tap that just triggered an animation or a page load does not come back as `ocr_no_match` on the first empty frame. The result then carries `waitedMs`. Leave it at 0 to read exactly once.

