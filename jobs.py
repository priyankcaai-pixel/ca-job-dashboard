import argparse
import json
import os
import re
import zipfile
from html import unescape
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import quote, urlsplit
from urllib.request import Request, urlopen
from xml.etree import ElementTree as XML

ROOT = Path(__file__).resolve().parent
WORKBOOK = ROOT.parent / "CA_Job_Search_Dashboard_Freshness.xlsx"
ROLE = re.compile(r"chartered accountant|\bca\b|accounting|accountant|audit|\btax\b|finance|financial|controller|treasury|\bfp\s*&\s*a\b", re.I)
INDIA = re.compile(r"\bindia\b|delhi|noida|pune|bhopal|indore|mumbai|bengaluru|bangalore|gurugram|gurgaon|hyderabad|chennai|kolkata|ahmedabad|jaipur|\b(?:KA|MH|DL|HR|UP|MP|TN|TS|GJ|WB)\s*,?\s*IN\b|, IN$", re.I)
CA = re.compile(r"(?i:\bchartered accountant(?:s|cy)?\b)|\bCA\b")
OPTIONAL = re.compile(r"\b(?:preferred|preferable|desirable|advantage|a plus|optional|nice to|ideally|intermediate|semi[- ]qualified|part[- ]qualified|pursuing|CA\s*\(?\s*inter\b|CA finalist|not required)\b|[/,]\s*(?:CPA|CMA|ACCA|MBA|CS|CFA|ICWA|ICWAI|CIMA|CWA|M\.?Com|B\.?Com)\b|(?:CPA|CMA|ACCA|MBA|CS|CFA|ICWA|ICWAI|CIMA|CWA)\s*/\s*(?:CA|chartered accountant)\b|\b(?:or|and/or|equivalent)\b", re.I)
REQUIRED = re.compile(r"\b(?:required|mandatory|must|qualified|qualification|minimum|essential|only|certification)\b|\d\+?\s*years?\s+(?:of\s+)?(?:post[- ]qualification|post[- ]CA|PQE)", re.I)
HEADERS = "company role location family fit resume stage action url resumeUrl mode experience salary posted listing notes freshness".split()


def ca_evidence(role, description):
    # Keep the qualifying line so a reader can check it against the source.
    description = unescape(unescape(description or ""))
    description = re.sub(r"<(?:br|/p|/li|/div|/h[1-6])\b[^>]*>", "\n", description, flags=re.I)
    description = re.sub(r"<[^>]+>", "", description)
    for raw in [role, *description.splitlines()]:
        line = " ".join(raw.split())
        if not CA.search(line) or OPTIONAL.search(line):
            continue
        if re.search(r"\bideal candidate\b", line, re.I) and not re.search(r"\b(?:must|required|mandatory)\b", line, re.I):
            continue
        if re.fullmatch(r"CA[.!]?", line) or REQUIRED.search(line) or re.fullmatch(r"(?:a )?chartered accountant(?: \(CA\))?[.!]?", line, re.I):
            return line[:350]
    return ""



def read_workbook(path):
    with zipfile.ZipFile(path) as archive:
        def read(name):
            return XML.fromstring(archive.read(name))

        strings = [
            "".join(node.text or "" for node in item.findall(".//{*}t"))
            for item in read("xl/sharedStrings.xml")
        ] if "xl/sharedStrings.xml" in archive.namelist() else []
        sheet = next(s for s in read("xl/workbook.xml").findall(".//{*}sheet") if s.get("name") == "Jobs")
        rel_id = next(value for key, value in sheet.attrib.items() if key.endswith("}id"))
        target = next(rel.get("Target") for rel in read("xl/_rels/workbook.xml.rels") if rel.get("Id") == rel_id)
        rows = []
        for row in read(target.lstrip("/") if target.startswith("/") else "xl/" + target).findall(".//{*}sheetData/{*}row"):
            if int(row.get("r")) <= 4:
                continue
            values = {}
            for cell in row.findall("{*}c"):
                col = re.match("[A-Z]+", cell.get("r")).group()
                if len(col) != 1 or col > "Q":
                    continue
                value = cell.findtext("{*}v", "")
                if cell.get("t") == "s" and value:
                    value = strings[int(value)]
                elif cell.get("t") == "inlineStr":
                    value = "".join(t.text or "" for t in cell.findall(".//{*}t"))
                values[HEADERS[ord(col) - ord("A")]] = value
            if values.get("company") and values.get("role"):
                rows.append(dict(values, source="Workbook", id="workbook:" + row.get("r")))
        return rows


def write_data(filename, variable, data):
    path = ROOT / "site" / filename
    pending = path.with_suffix(".tmp")
    pending.write_text("window." + variable + " = " + json.dumps(data, ensure_ascii=True) + ";\n", encoding="utf-8")
    pending.replace(path)


def get_json(url, token=None):
    headers = {"Accept": "application/json", "User-Agent": "CA-Job-Portal/1.0"}
    if token:
        headers["Authorization"] = "Bearer " + token
    with urlopen(Request(url, headers=headers), timeout=15) as response:
        return json.load(response)


def fetch(source):
    kind = source["type"]
    company = source["company"]
    board = quote(source.get("board", ""), safe="")
    if kind == "greenhouse":
        data = get_json(f"https://boards-api.greenhouse.io/v1/boards/{board}/jobs?content=true")["jobs"]
        records = [dict(role=j["title"], location=j["location"]["name"], url=j["absolute_url"], description=j.get("content", "")) for j in data]
    elif kind == "lever":
        records = []
        for offset in range(0, 5000, 100):
            page = get_json(f"https://api.lever.co/v0/postings/{board}?mode=json&limit=100&skip={offset}")
            records.extend(dict(role=j["text"], location=", ".join(j["categories"].get("allLocations") or [j["categories"].get("location") or ""]), url=j["hostedUrl"], mode=j.get("workplaceType", ""), description="\n".join([j.get("descriptionPlain") or "", *[item.get("content", "") for item in j.get("lists", [])], j.get("additionalPlain") or ""])) for j in page)
            if len(page) < 100:
                break
    elif kind == "smartrecruiters":
        records = []
        for offset in range(0, 5000, 100):
            page = get_json(f"https://api.smartrecruiters.com/v1/companies/{board}/postings?country=in&limit=100&offset={offset}")
            records.extend(dict(role=j["name"], location=", ".join(filter(None, (j["location"].get("city"), j["location"].get("region"), j["location"].get("country")))), url=f"https://jobs.smartrecruiters.com/{board}/{j['id']}", posted=j.get("releasedDate", ""), detail=j.get("ref")) for j in page["content"])
            if offset + len(page["content"]) >= page["totalFound"] or not page["content"]:
                break
    elif kind == "ashby":
        data = get_json(f"https://api.ashbyhq.com/posting-api/job-board/{board}")["jobs"]
        records = [
            dict(role=j["title"], location=", ".join([j["location"], *[
                place["location"] for place in j.get("secondaryLocations", [])
            ]]), url=j["jobUrl"], posted=j.get("publishedAt", ""),
                 mode=j.get("workplaceType", ""), description=j.get("descriptionPlain", ""))
            for j in data if j.get("isListed")
        ]
    elif kind == "json":
        url = source.get("url") or os.environ[source["urlEnv"]]
        token = os.environ[source["tokenEnv"]] if source.get("tokenEnv") else None
        if urlsplit(url).scheme != "https":
            raise ValueError("JSON feeds require HTTPS")
        records = get_json(url, token)
    else:
        raise ValueError("Unknown feed type")
    jobs = []
    for record in records:
        role, location, url = (record.get(key) or "" for key in ("role", "location", "url"))
        if not INDIA.search(location) or urlsplit(url).scheme != "https":
            continue
        description = record.get("description", "")
        if kind == "smartrecruiters" and ROLE.search(role) and record.get("detail"):
            details = get_json(record["detail"]).get("jobAd", {}).get("sections", {})
            description = "\n".join(details.get(key, {}).get("text", "") for key in ("qualifications", "jobDescription"))
        evidence = ca_evidence(role, description)
        if not evidence:
            continue
        jobs.append(dict(
            id=url, company=record.get("company") or company, role=role, location=location,
            url=url, source=source.get("label", company + " careers"), stage="Review",
            posted=record.get("posted", ""), mode=record.get("mode", ""), listing="Published", caEvidence=evidence,
        ))
    return jobs


def refresh():
    sources = json.loads((ROOT / "sources.json").read_text(encoding="utf-8"))
    status, jobs = [], {}
    snapshot = ROOT / "site" / "vacancies.js"
    previous = {}
    if snapshot.exists():
        previous = json.loads(snapshot.read_text(encoding="utf-8").removeprefix("window.vacancies = ").strip().removesuffix(";")).get("feeds", {})

    def run(source):
        label = source.get("label", source["company"] + " careers")
        key = ":".join([source["type"], source.get("board", ""), label])
        now = datetime.now(UTC).isoformat()
        try:
            return key, dict(label=label, jobs=fetch(source), checked=now, ok=True)
        except Exception as exc:
            cached = previous.get(key, {})
            return key, dict(label=label, jobs=[job for job in cached.get("jobs", []) if job.get("caEvidence")], checked=cached.get("checked"), ok=False, error=type(exc).__name__)

    with ThreadPoolExecutor(max_workers=5) as workers:
        feeds = dict(workers.map(run, sources))
    for feed in feeds.values():
        status.append({key: value for key, value in feed.items() if key != "jobs"} | {"count": len(feed["jobs"])})
        for job in feed["jobs"]:
            jobs.setdefault(job["id"], job)
    write_data("vacancies.js", "vacancies", dict(jobs=list(jobs.values()), status=status, feeds=feeds))
    for item in status:
        print(item["label"], item["count"], "current" if item["ok"] else "fetch failed (" + item["error"] + ")")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["import", "refresh"])
    parser.add_argument("--workbook", type=Path, default=WORKBOOK)
    args = parser.parse_args()
    if args.command == "import":
        records = read_workbook(args.workbook)
        write_data("workbook.js", "workbookJobs", records)
        print(f"Imported {len(records)} records")
    else:
        refresh()
