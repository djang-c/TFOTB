"""Small, deliberately conservative text normalisers.

`direction_class` maps the free-text direction an extractor wrote ("increased", "down-regulated",
"reduced") to up / down, or None when it is not clearly one of them. Unknown stays None: it is never
guessed, and None never counts as agreeing or disagreeing.
"""

from __future__ import annotations

import re

_UP = re.compile(r"\b(up|upregulat\w*|up-regulat\w*|increas\w*|elevat\w*|higher|rais\w*|enhanc\w*|accumulat\w*|gain)\b", re.IGNORECASE)
_DOWN = re.compile(r"\b(down|downregulat\w*|down-regulat\w*|decreas\w*|reduc\w*|lower\w*|loss|deplet\w*|diminish\w*|impair\w*)\b", re.IGNORECASE)


def direction_class(text: str | None) -> str | None:
    if not text:
        return None
    up, down = bool(_UP.search(text)), bool(_DOWN.search(text))
    if up == down:  # neither, or both (e.g. "increase then decrease"): not a clear direction
        return None
    return "up" if up else "down"
