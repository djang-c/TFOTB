"""Q2 "What useful work already exists?": studies registered on ClinicalTrials.gov, no language model.

Rules:
- ClinicalTrials.gov expands condition searches broadly ("Niemann-Pick disease type C" also returns
  acid sphingomyelinase and lysosomal acid lipase trials). A study is kept only when one of its
  listed conditions is, word for word after normalisation, a name of this disease in MONDO; that
  condition text is quoted as the claim's source span. Everything else is counted as screened out.
- Order is practical (open studies first, then most recently updated), never biological.
- Status is verbatim from the record, with the record URL and the retrieval date.
- Terms (read by the owner 2026-10-03, last updated 2023-01-31): attribute ClinicalTrials.gov as a
  U.S. Government database, keep data current (24 h cache), show the date each record was last
  updated there, and state our modifications (filtering and reformatting; see MODIFICATIONS).
"""

from __future__ import annotations

import hashlib
import json
import time
import urllib.parse
import urllib.request
from datetime import UTC, datetime
from typing import Any

from atlas.resolver import normalize
from atlas.schemas import (
    AssetResult,
    Claim,
    ClaimStatus,
    Contact,
    SourceCoverage,
    SourceStatus,
    SourceType,
)

API = "https://clinicaltrials.gov/api/v2/studies"
FIELDS = ("NCTId,BriefTitle,OverallStatus,Condition,StudyType,Phase,LeadSponsorName,"
          "StartDate,EnrollmentCount,LastUpdatePostDate,PatientRegistry")
OPEN = {"RECRUITING", "NOT_YET_RECRUITING", "ENROLLING_BY_INVITATION", "ACTIVE_NOT_RECRUITING", "AVAILABLE"}
CACHE_SECONDS = 24 * 3600
PAGE_SIZE = 100
MAX_SHOWN = 50
MODIFICATIONS = ("Only studies that list this disease by name are shown; titles and conditions are verbatim; "
                 "status is shown in lower case without underscores; order is ours (open first, then most recently updated).")


class TrialsSource:
    def __init__(self, fetch=None) -> None:
        self._fetch = fetch or _http_get
        self._cache: dict[str, tuple[float, dict[str, Any]]] = {}
        self.claims: dict[str, dict[str, Any]] = {}  # every ASSET_RELEVANT_TO claim served so far

    def for_disease(self, disease_id: str, label: str, names: set[str], query_names: list[str] | None = None) -> dict[str, Any]:
        hit = self._cache.get(disease_id)
        if hit and time.time() - hit[0] < CACHE_SECONDS:
            return hit[1]
        out = self._build(disease_id, label, names, query_names or [label])
        self.claims.update(out["claims"])
        self._cache[disease_id] = (time.time(), out)
        return out

    def _build(self, disease_id: str, label: str, names: set[str], query_names: list[str]) -> dict[str, Any]:
        today = datetime.now(UTC).date()
        # Registries rarely use the MONDO label, so the label and the exact synonyms are all searched.
        cond = " OR ".join(f'"{n}"' for n in query_names)
        params = {"query.cond": cond, "pageSize": PAGE_SIZE, "countTotal": "true", "fields": FIELDS}
        url = f"{API}?{urllib.parse.urlencode(params)}"
        try:
            data = self._fetch(url)
        except (OSError, ValueError) as e:  # network, HTTP or JSON failure: say so, never pretend zero
            cov = SourceCoverage(source="ClinicalTrials.gov", status=SourceStatus.failed, error=str(e)[:200])
            return {"assets": [], "claims": {}, "coverage": cov.model_dump(mode="json"), "query": url}
        wanted = {normalize(n) for n in names | {label}}
        studies = data.get("studies", [])
        assets, claims = [], {}
        for s in studies:
            p = s.get("protocolSection", {})
            nct = p.get("identificationModule", {}).get("nctId", "")
            conditions = p.get("conditionsModule", {}).get("conditions", [])
            match = next((c for c in conditions if normalize(c) in wanted), None)
            if not nct or match is None:
                continue
            record = f"https://clinicaltrials.gov/study/{nct}"
            digest = hashlib.sha256(f"{nct}|{disease_id}|{match}".encode()).hexdigest()[:16]
            claim = Claim(
                claim_id=f"CLAIM:ctgov-{digest}", subject_id=f"NCT:{nct[3:]}", predicate="ASSET_RELEVANT_TO",
                object_id=disease_id, source_url=record, source_span=match, source_type=SourceType.database_record,
                status=ClaimStatus.reported_observation, lineage_id=f"NCT:{nct[3:]}",
                context={"study_title": p.get("identificationModule", {}).get("briefTitle") or nct,
                         "listed_conditions": "; ".join(conditions)}, extraction_method="structured_field",
                retrieved_at=today,
            )
            claims[claim.claim_id] = claim.model_dump(mode="json")
            status = p.get("statusModule", {})
            design = p.get("designModule", {})
            phases = [x for x in design.get("phases", []) if x != "NA"]
            kind = (design.get("studyType") or "").lower().replace("_", " ")
            if design.get("patientRegistry"):
                kind = "patient registry (observational)"
            enrol = design.get("enrollmentInfo", {}).get("count")
            sponsor = p.get("sponsorCollaboratorsModule", {}).get("leadSponsor", {}).get("name")
            updated = status.get("lastUpdatePostDateStruct", {}).get("date", "")
            asset = AssetResult(
                asset_id=f"ASSET:ctgov-{nct}", asset_kind="clinical_study",
                label=p.get("identificationModule", {}).get("briefTitle") or nct, source_url=record,
                relevance_claim_ids=(claim.claim_id,),
                access_conditions="Public registry record; access to participant data is decided by the sponsor"
                                  + (f" ({sponsor})" if sponsor else ""),
                status=(status.get("overallStatus") or "").replace("_", " ").lower() or None,
                status_source_url=record, status_checked_at=today,
                reuse_limits=tuple(x for x in (
                    f"{kind} study" + (f", {', '.join(phases).lower().replace('phase', 'phase ')}" if phases else "") if kind else "",
                    f"{enrol} participants" if enrol else "",
                    "other listed conditions: " + "; ".join(c for c in conditions if c != match) if len(conditions) > 1 else "",
                ) if x),
                contact=Contact(label=f"{nct} on ClinicalTrials.gov", url=record, source_url=record, verified_at=today),
                needs_expert_review=("whether the design, eligibility or data could be reused for your disease",),
                ranking_reasons=tuple(x for x in (
                    f"lists “{match}” as a condition",
                    "open" if status.get("overallStatus") in OPEN else "",
                    f"last updated on ClinicalTrials.gov {updated}" if updated else "",
                ) if x),
            )
            assets.append((status.get("overallStatus") in OPEN, updated, asset))
        assets.sort(key=lambda t: (not t[0], _neg_date(t[1]), t[2].asset_id))
        cov = SourceCoverage(source="ClinicalTrials.gov", version=f"API v2, retrieved {today.isoformat()}",
                             status=SourceStatus.ok, fetched=len(studies), screened=len(assets))
        return {
            "assets": [a.model_dump(mode="json") for _, _, a in assets[:MAX_SHOWN]],
            "total": len(assets),
            "registry_total": data.get("totalCount"),
            "claims": claims,
            "coverage": cov.model_dump(mode="json"),
            "query": url,
            "attribution": "ClinicalTrials.gov, a database of the U.S. National Library of Medicine",
            "modifications": MODIFICATIONS,
        }


def _neg_date(d: str) -> str:
    """Sort key: most recent first, using string inversion of an ISO date."""
    return "".join(chr(255 - ord(c)) for c in d)


def _http_get(url: str) -> dict[str, Any]:
    req = urllib.request.Request(url, headers={"User-Agent": "the-flight-of-the-buffalo/1.0 (research; hackathon)"})
    with urllib.request.urlopen(req, timeout=8) as resp:
        return json.loads(resp.read().decode())
