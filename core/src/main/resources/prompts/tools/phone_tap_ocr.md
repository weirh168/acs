Tap a piece of text that is on screen, using on-device OCR instead of the accessibility tree. The line's center is tapped.

Use it when the thing you want is drawn rather than exposed: canvas and game UIs, Flutter/React-Native surfaces, or an item you only saw in `ocrOnly` from phone_observe. When the target has a normal accessibility node, `phone_tap` by ref is still more reliable.

`text` is what you see on screen (the line, or a distinctive part of it). `region` narrows the search to one area, `left,top,right,bottom` in 0-999 coordinates — useful when two lists show the same words and only one of them should be tapped. With `exact: true` the whole line must equal it; by default a line containing it is enough, and the shortest matching line wins (usually the button itself).

The result says which line was matched (`matchedText`, `x`/`y` in 0–999) and how many other lines matched (`alsoMatched`). If nothing matched you get `ocr_no_match` with a few nearby lines: read them and retry with the exact wording, or use phone_observe.
