"""Source ingestion tests. All XML and API responses are SYNTHETIC; no network."""

import json

import pytest

from atlas.sources import SourceError, fetch_full_text

XML = b"""<article><front><article-meta><author-notes><corresp><p>Corresponding author someone@example.org</p></corresp></author-notes><title-group><article-title>A synthetic title</article-title></title-group>
<abstract><p>Synthetic abstract sentence.</p></abstract></article-meta></front>
<body><sec><title>Intro</title><p>The most common NCL is juvenile CLN3 disease (JNCL), a disorder caused by
mutations in the CLN3 gene.<xref ref-type="bibr" rid="b5">5</xref> See <xref ref-type="fig" rid="f1">Fig. 1</xref> for the
cation-independent receptor and <italic>LE/Lys</italic> data.</p>
<p>Second paragraph<list><list-item><p>nested item</p></list-item></list>.</p></sec></body>
<back><ref-list><ref><mixed-citation>Do not read this reference</mixed-citation></ref></ref-list></back></article>"""


def fake(pmid="1", oa="Y", pmcid="PMC9", xml=XML, hits=True):
    def fetch(url: str) -> bytes:
        if "/search?" in url:
            res = [{"pmid": pmid, "pmcid": pmcid, "isOpenAccess": oa, "license": "cc by", "title": "T"}] if hits else []
            return json.dumps({"resultList": {"result": res}}).encode()
        assert url.endswith(f"/{pmcid}/fullTextXML")
        return xml

    return fetch


def test_clean_text_has_no_line_break_artifacts_or_citation_markers_and_no_reference_list():
    ft = fetch_full_text("1", fake())
    assert "juvenile CLN3 disease (JNCL), a disorder caused by\nmutations" not in ft.text
    assert "caused by mutations in the CLN3 gene. See Fig. 1 for the cation-independent receptor and LE/Lys data." in " ".join(ft.text.split())
    assert "Do not read this reference" not in ft.text
    assert "someone@example.org" not in ft.text  # contact details are skipped
    assert ft.text.splitlines()[0] == "A synthetic title" and "Synthetic abstract sentence." in ft.text
    assert (ft.pmcid, ft.license) == ("PMC9", "cc by")


def test_nested_paragraph_is_not_duplicated():
    assert fetch_full_text("1", fake()).text.count("nested item") == 1


def test_not_found_and_not_open_access_raise_instead_of_guessing():
    with pytest.raises(SourceError, match="not found"):
        fetch_full_text("1", fake(hits=False))
    with pytest.raises(SourceError, match="no open-access"):
        fetch_full_text("1", fake(oa="N"))


def test_xml_without_paragraphs_raises():
    with pytest.raises(SourceError, match="no paragraphs"):
        fetch_full_text("1", fake(xml=b"<article><body></body></article>"))
