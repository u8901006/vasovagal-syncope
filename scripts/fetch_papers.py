#!/usr/bin/env python3
"""
Fetch latest vasovagal syncope research papers from PubMed E-utilities API.
Covers cardiology, autonomic neuroscience, pediatrics, psychology,
nutrition, emergency medicine, and rehabilitation literature.
"""

import json
import sys
import argparse
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from urllib.request import urlopen, Request
from urllib.error import URLError
from urllib.parse import quote_plus

PUBMED_SEARCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
PUBMED_FETCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"

CORE_BLOCK = (
    '("Syncope, Vasovagal"[Mesh] OR "vasovagal syncope"[tiab] OR '
    '"neurocardiogenic syncope"[tiab] OR "neurally mediated syncope"[tiab] OR '
    '"neurally mediated faint*"[tiab] OR "reflex syncope"[tiab] OR '
    '"vasodepressor syncope"[tiab] OR "cardioinhibitory syncope"[tiab])'
)

SEARCH_QUERIES = [
    CORE_BLOCK,
    f'{CORE_BLOCK} AND (review[pt] OR "systematic review"[tiab] OR meta-analysis[pt])',
    f'{CORE_BLOCK} AND ("Tilt-Table Test"[Mesh] OR "head-up tilt"[tiab] OR HUTT[tiab])',
    f'{CORE_BLOCK} AND ("Autonomic Nervous System"[Mesh] OR autonomic[tiab] OR baroreflex[tiab] OR "heart rate variability"[tiab] OR HRV[tiab])',
    f'{CORE_BLOCK} AND ("cerebral blood flow"[tiab] OR "cerebral perfusion"[tiab] OR NIRS[tiab] OR fNIRS[tiab] OR EEG[tiab])',
    f'{CORE_BLOCK} AND ("Child"[Mesh] OR "Adolescent"[Mesh] OR child*[tiab] OR pediatric*[tiab] OR adolescent*[tiab])',
    f'{CORE_BLOCK} AND ("Anxiety"[Mesh] OR anxiety[tiab] OR panic[tiab] OR fear[tiab] OR "blood-injection-injury"[tiab] OR "needle phobia"[tiab] OR interoception[tiab])',
    f'{CORE_BLOCK} AND ("psychogenic pseudosyncope"[tiab] OR "functional neurological disorder"[tiab])',
    f'{CORE_BLOCK} AND ("Quality of Life"[Mesh] OR "quality of life"[tiab] OR disability[tiab] OR absenteeism[tiab])',
    f'{CORE_BLOCK} AND ("Social Determinants of Health"[Mesh] OR socioeconomic[tiab] OR "healthcare utilization"[tiab] OR "emergency department"[tiab])',
    f'{CORE_BLOCK} AND (hydration[tiab] OR dehydration[tiab] OR sodium[tiab] OR salt[tiab] OR vitamin*[tiab] OR iron[tiab] OR anemia[tiab])',
    f'{CORE_BLOCK} AND (education[tiab] OR "counter-pressure"[tiab] OR handgrip[tiab] OR "tilt training"[tiab] OR exercise[tiab] OR "compression garment*"[tiab])',
    f'{CORE_BLOCK} AND (fludrocortisone[tiab] OR midodrine[tiab] OR beta-blocker*[tiab] OR SSRI[tiab] OR pacemaker[tiab] OR pacing[tiab] OR cardioneuroablation[tiab])',
    f'{CORE_BLOCK} AND (injury[tiab] OR fall*[tiab] OR fracture*[tiab] OR driving[tiab] OR occupational[tiab])',
    f'{CORE_BLOCK} AND ("emergency department"[tiab] OR "emergency medicine"[tiab] OR "risk stratification"[tiab])',
]

JOURNALS = [
    "European Heart Journal",
    "Europace",
    "Heart Rhythm",
    "JACC: Clinical Electrophysiology",
    "Circulation",
    "Journal of Cardiovascular Electrophysiology",
    "Autonomic Neuroscience",
    "Clinical Autonomic Research",
    "Clinical Neurophysiology",
    "Neurology",
    "Journal of Neurology",
    "Frontiers in Neurology",
    "Frontiers in Neuroscience",
    "Brain Sciences",
    "Physiological Reports",
    "Pediatrics",
    "The Journal of Pediatrics",
    "JAMA Pediatrics",
    "Pediatric Cardiology",
    "Cardiology in the Young",
    "Frontiers in Pediatrics",
    "Annals of Emergency Medicine",
    "Emergency Medicine Journal",
    "BMJ",
    "JAMA",
    "Mayo Clinic Proceedings",
    "Age and Ageing",
    "Psychosomatic Medicine",
    "Journal of Psychosomatic Research",
    "Psychophysiology",
    "Journal of Anxiety Disorders",
    "Behaviour Research and Therapy",
    "Nutrients",
    "American Journal of Clinical Nutrition",
    "Hypertension",
    "Cochrane Database of Systematic Reviews",
    "PLOS ONE",
    "Scientific Reports",
    "Frontiers in Physiology",
    "Journal of Clinical Medicine",
]

HEADERS = {"User-Agent": "VasovagalSyncopeBot/1.0 (research aggregator)"}


def build_query(days: int = 7) -> str:
    lookback = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y/%m/%d")
    date_part = f'"{lookback}"[Date - Publication] : "3000"[Date - Publication]'
    return f"({CORE_BLOCK}) AND {date_part}"


def search_papers(query: str, retmax: int = 50) -> list[str]:
    params = (
        f"?db=pubmed&term={quote_plus(query)}&retmax={retmax}&sort=date&retmode=json"
    )
    url = PUBMED_SEARCH + params
    try:
        req = Request(url, headers=HEADERS)
        with urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode())
        return data.get("esearchresult", {}).get("idlist", [])
    except Exception as e:
        print(f"[ERROR] PubMed search failed: {e}", file=sys.stderr)
        return []


def fetch_details(pmids: list[str]) -> list[dict]:
    if not pmids:
        return []
    ids = ",".join(pmids)
    params = f"?db=pubmed&id={ids}&retmode=xml"
    url = PUBMED_FETCH + params
    try:
        req = Request(url, headers=HEADERS)
        with urlopen(req, timeout=60) as resp:
            xml_data = resp.read().decode()
    except Exception as e:
        print(f"[ERROR] PubMed fetch failed: {e}", file=sys.stderr)
        return []

    papers = []
    try:
        root = ET.fromstring(xml_data)
        for article in root.findall(".//PubmedArticle"):
            medline = article.find(".//MedlineCitation")
            art = medline.find(".//Article") if medline else None
            if art is None:
                continue

            title_el = art.find(".//ArticleTitle")
            title = ""
            if title_el is not None:
                title = "".join(title_el.itertext()).strip()

            abstract_parts = []
            for abs_el in art.findall(".//Abstract/AbstractText"):
                label = abs_el.get("Label", "")
                text = "".join(abs_el.itertext()).strip()
                if label and text:
                    abstract_parts.append(f"{label}: {text}")
                elif text:
                    abstract_parts.append(text)
            abstract = " ".join(abstract_parts)[:2000]

            journal_el = art.find(".//Journal/Title")
            journal = (
                (journal_el.text or "").strip()
                if journal_el is not None and journal_el.text
                else ""
            )

            pub_date = art.find(".//PubDate")
            date_str = ""
            if pub_date is not None:
                year = pub_date.findtext("Year", "")
                month = pub_date.findtext("Month", "")
                day = pub_date.findtext("Day", "")
                parts = [p for p in [year, month, day] if p]
                date_str = " ".join(parts)

            pmid_el = medline.find(".//PMID")
            pmid = pmid_el.text if pmid_el is not None else ""
            link = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/" if pmid else ""

            keywords = []
            for kw in medline.findall(".//KeywordList/Keyword"):
                if kw.text:
                    keywords.append(kw.text.strip())

            papers.append(
                {
                    "pmid": pmid,
                    "title": title,
                    "journal": journal,
                    "date": date_str,
                    "abstract": abstract,
                    "url": link,
                    "keywords": keywords,
                }
            )
    except ET.ParseError as e:
        print(f"[ERROR] XML parse failed: {e}", file=sys.stderr)

    return papers


def load_summarized_pmids() -> set:
    pmids = set()
    try:
        import glob
        for f in glob.glob("docs/vasovagal-*.html"):
            pass
    except Exception:
        pass
    return pmids


def main():
    parser = argparse.ArgumentParser(description="Fetch VVS papers from PubMed")
    parser.add_argument("--days", type=int, default=7, help="Lookback days")
    parser.add_argument("--max-papers", type=int, default=40, help="Max papers to fetch")
    parser.add_argument("--output", default="-", help="Output file (- for stdout)")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = parser.parse_args()

    print(
        f"[INFO] Searching PubMed for VVS papers from last {args.days} days...",
        file=sys.stderr,
    )

    main_query = build_query(days=args.days)
    all_pmids = search_papers(main_query, retmax=args.max_papers)

    if len(all_pmids) < args.max_papers // 2:
        print("[INFO] Main query returned few results, trying supplementary queries...", file=sys.stderr)
        for sq in SEARCH_QUERIES[:5]:
            lookback = (datetime.now(timezone.utc) - timedelta(days=args.days)).strftime("%Y/%m/%d")
            date_part = f'"{lookback}"[Date - Publication] : "3000"[Date - Publication]'
            extra_pmids = search_papers(f"{sq} AND {date_part}", retmax=10)
            for p in extra_pmids:
                if p not in all_pmids:
                    all_pmids.append(p)

    all_pmids = all_pmids[:args.max_papers]
    print(f"[INFO] Found {len(all_pmids)} unique papers", file=sys.stderr)

    if not all_pmids:
        print("NO_CONTENT", file=sys.stderr)
        tz_taipei = timezone(timedelta(hours=8))
        if args.json:
            output_data = {
                "date": datetime.now(tz_taipei).strftime("%Y-%m-%d"),
                "count": 0,
                "papers": [],
            }
            out_str = json.dumps(output_data, ensure_ascii=False, indent=2)
            if args.output == "-":
                print(out_str)
            else:
                with open(args.output, "w", encoding="utf-8") as f:
                    f.write(out_str)
                print(f"[INFO] Saved to {args.output}", file=sys.stderr)
        return

    papers = fetch_details(all_pmids)
    print(f"[INFO] Fetched details for {len(papers)} papers", file=sys.stderr)

    tz_taipei = timezone(timedelta(hours=8))
    output_data = {
        "date": datetime.now(tz_taipei).strftime("%Y-%m-%d"),
        "count": len(papers),
        "papers": papers,
    }

    out_str = json.dumps(output_data, ensure_ascii=False, indent=2)

    if args.output == "-":
        print(out_str)
    else:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(out_str)
        print(f"[INFO] Saved to {args.output}", file=sys.stderr)


if __name__ == "__main__":
    main()
