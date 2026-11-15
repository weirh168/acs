See how many tokens this task has already spent, how much budget is left, and how much this phone used today.

`run` is this task: `inputTokens`, `outputTokens`, `cachedInputTokens` (cached reads are part of the input, do not add them again), `tokens` (input + output), `calls` (model calls, retries counted once) and `httpCalls` (actual requests). When the task has a token budget you also get `budget` and `remaining` — near the end, wrap up with what you have instead of starting long explorations.

`today` is the whole phone for the local day, all providers and all tasks together; it is missing when the app cannot read its ledger.

Reading it costs nothing and makes no model call. Use it when a task is getting long, when the user asks about cost, or before deciding whether to keep exploring.
