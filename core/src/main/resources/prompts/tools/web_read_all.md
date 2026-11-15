Read a list on the current page as structured items: pricing tables, search results, order lists, card feeds. Each item comes back as `title` (heading or first link, may be empty), `text` (its visible text) and `link` (first absolute href, may be empty), plus `count` (returned) and `found` (how many the page has).

Use this instead of web_read_page when the page is a list: read_page flattens the whole page into one text and the item boundaries blur, so you cannot tell which price belongs to which product.

`selector` (optional) is CSS for ONE item, e.g. `li.result`, `.card`, `table tbody tr`. Without it the tool finds the largest group of similar siblings itself and says `autoDetected: true`; if the auto pick is wrong, look at the elements from web_observe and pass the selector of one item.

Reads only: it does not scroll, load more, or click. To get more items, scroll with web_scroll and call it again. Long items are cut at 600 characters.
