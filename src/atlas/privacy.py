"""Detect the synthetic/private case marker (`CASE-SYN-<digits>`) however it is typed.

A literal `"CASE-SYN-" in text` check is bypassed by lower case, zero-width characters, non-breaking or
full-width hyphens and spaces. This normalises first (NFKC, case-fold, zero-width characters removed) and
then looks for the marker with any dash or space between its parts. It is defence in depth only: the real
protection is that case data lives in `CaseStore` and is never passed to a public store. A tripwire cannot
recognise real identifiers (PHI/PII), which must never be entered at all.
"""

from __future__ import annotations

import re
import unicodedata

# zero-width space/joiners, direction marks, word joiner, BOM, soft hyphen (written as code points on purpose)
_ZERO_WIDTH = dict.fromkeys([0x200B, 0x200C, 0x200D, 0x200E, 0x200F, 0x2060, 0xFEFF, 0x00AD], None)
# dash-like separators: hyphen-minus, U+2010..U+2015 (hyphens and dashes), U+2212 (minus sign)
_SEP = r"[\s_\-‐-―−]*"
_MARKER = re.compile(rf"case{_SEP}syn{_SEP}\d")


def contains_private_marker(text: str) -> bool:
    t = unicodedata.normalize("NFKC", text).translate(_ZERO_WIDTH).casefold()
    return bool(_MARKER.search(t))
