"""Patient groups per disease, as listed by GARD (NIH/NCATS Genetic and Rare Diseases Information Center).

Rules:
- A disease is looked up through MONDO's own GARD cross-reference, and the GARD record is accepted only
  if its MONDO field names the same disease. Anything else is rejected and counted, never guessed.
- Names and websites are shown exactly as GARD lists them. Nothing is generated; nothing is checked by
  us. GARD's disclaimer (read by the owner 2026-10-03): listings are for information only, are not an
  endorsement, and come with no warranty. The UI says so next to the list.
- Source: the JSON files the GARD website itself loads. They are not a documented API and may change;
  a failure shows as "could not be checked", never as "no groups".
"""

from __future__ import annotations

import json
import time
import urllib.request
from datetime import UTC, datetime
from typing import Any

SINGLE = "https://rarediseases.info.nih.gov/assets/singles/{num}.json"
ACCOUNTS = "https://rarediseases.info.nih.gov/assets/related/all-account-data.json"
PAGE = "https://rarediseases.info.nih.gov/diseases/{num}/{slug}"
CACHE_SECONDS = 24 * 3600
NOTE = ("Listed by GARD (NIH). A listing is not an endorsement by NIH or by us, and we have not checked "
        "these groups. Names and links are shown as GARD gives them.")


def _site(url: str) -> str:
    u = (url or "").lower().strip().rstrip("/")
    for p in ("https://", "http://", "www."):
        u = u.removeprefix(p)
    return u


class GardSource:
    def __init__(self, fetch=None) -> None:
        self._fetch = fetch or _http_get
        self._cache: dict[str, tuple[float, dict[str, Any]]] = {}
        self._accounts: tuple[float, dict[str, dict[str, Any]]] | None = None

    def _account_index(self) -> dict[str, dict[str, Any]]:
        if self._accounts and time.time() - self._accounts[0] < CACHE_SECONDS:
            return self._accounts[1]
        idx: dict[str, dict[str, Any]] = {}
        try:
            for row in self._fetch(ACCOUNTS):
                a = row.get("acct") or {}
                if a.get("Website"):
                    idx[_site(a["Website"])] = a
                if a.get("Name"):
                    idx[a["Name"].strip().lower()] = a
        except (OSError, ValueError):
            idx = {}
        self._accounts = (time.time(), idx)
        return idx

    def for_disease(self, mondo_id: str, gard_ids: list[str]) -> dict[str, Any]:
        hit = self._cache.get(mondo_id)
        if hit and time.time() - hit[0] < CACHE_SECONDS:
            return hit[1]
        out = self._build(mondo_id, gard_ids)
        self._cache[mondo_id] = (time.time(), out)
        return out

    def _build(self, mondo_id: str, gard_ids: list[str]) -> dict[str, Any]:
        today = datetime.now(UTC).date().isoformat()
        base = {"note": NOTE, "retrieved": today, "groups": [], "pages": [], "rejected": 0}
        if not gard_ids:
            return {**base, "status": "no_xref"}
        accounts = self._account_index()
        groups: dict[str, dict[str, Any]] = {}
        failed = 0
        for gid in sorted(gard_ids):
            num = int(gid.split(":", 1)[1])
            try:
                rec = self._fetch(SINGLE.format(num=num))
            except (OSError, ValueError):
                failed += 1
                continue
            if rec.get("MONDO_ID__c") != mondo_id:  # the record must name this disease itself
                base["rejected"] += 1
                continue
            base["pages"].append({"label": rec.get("Name") or gid,
                                  "url": PAGE.format(num=num, slug=rec.get("encodedName") or "")})
            for o in rec.get("Organization_Supported_Diseases__c") or []:
                name, site = (o.get("Account_Name__c") or "").strip(), (o.get("Website__c") or "").strip()
                if not name:
                    continue
                acct = accounts.get(_site(site)) or accounts.get(name.lower()) or {}
                groups.setdefault(name, {
                    "name": name,
                    "website": site if site.startswith(("https://", "http://")) else None,
                    "country": acct.get("Country__c"),
                    "registry_url": acct.get("Patient_Registry_URL__c"),
                    "kind": (acct.get("RecordType") or {}).get("Name"),
                    "gard_id": gid,
                })
        status = "failed" if failed and not base["pages"] else "ok"
        return {**base, "status": status, "groups": sorted(groups.values(), key=lambda g: g["name"].lower())}


def _http_get(url: str) -> Any:
    req = urllib.request.Request(url, headers={"User-Agent": "the-flight-of-the-buffalo/1.0 (research; hackathon)"})
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read().decode())
