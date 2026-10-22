import json
import os
import re
import smtplib
import ssl
import sys
import time
from datetime import datetime, timezone
from email.message import EmailMessage
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

try:
    from jobspy import scrape_jobs
except ImportError:
    print("ERROR: python-jobspy is not installed. Run: pip install -r requirements.txt")
    raise

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
DATA_DIR.mkdir(exist_ok=True)
OUTPUT_JSON = DATA_DIR / "jobs.json"
OUTPUT_CSV = DATA_DIR / "jobs.csv"
STATUS_JSON = DATA_DIR / "source_status.json"

# Adjust these lists if you want more role variants.
ROLE_SEARCHES = [
    "Procurement Manager",
    "Purchase Manager",
    "Sourcing Manager",
    "Strategic Sourcing Manager",
    "Procurement Lead",
    "Purchase Head",
    "Supply Chain Manager",
    "Vendor Development Manager",
]
LOCATIONS = [
    ("India", "India"),
    ("Punjab, India", "Punjab"),
]
SITES = ["linkedin", "indeed", "naukri", "glassdoor"]
RESULTS_PER_SEARCH = int(os.getenv("RESULTS_PER_SEARCH", "25"))
HOURS_OLD = int(os.getenv("HOURS_OLD", "168"))  # last 7 days; change to 720 for 30 days

def clean(value):
    if value is None:
        return ""
    try:
        if str(value).lower() == "nan":
            return ""
    except Exception:
        pass
    return str(value).strip()

def safe_url(url):
    url = clean(url)
    if not url:
        return ""
    try:
        p = urlsplit(url)
        # Keep query parameters because some apply links need them.
        return urlunsplit((p.scheme, p.netloc, p.path, p.query, ""))
    except Exception:
        return url

def first(row, *keys):
    for key in keys:
        value = row.get(key, "")
        if clean(value):
            return value
    return ""

def normalize_row(row, search_term, search_location):
    d = row.to_dict() if hasattr(row, "to_dict") else dict(row)
    url = safe_url(first(d, "job_url", "job_url_direct", "url"))
    title = clean(first(d, "title", "job_title"))
    company = clean(first(d, "company", "company_name"))
    location = clean(first(d, "location"))
    site = clean(first(d, "site", "source")).lower()
    description = clean(first(d, "description"))
    posted = clean(first(d, "date_posted", "date"))
    salary_min = clean(first(d, "min_amount", "salary_min"))
    salary_max = clean(first(d, "max_amount", "salary_max"))
    currency = clean(first(d, "currency")) or "INR"
    interval = clean(first(d, "interval", "salary_interval"))
    salary = ""
    if salary_min or salary_max:
        salary = f"{currency} {salary_min or '?'}–{salary_max or '?'}"
        if interval:
            salary += f" / {interval}"
    return {
        "id": url or f"{site}|{title}|{company}|{location}",
        "title": title,
        "company": company,
        "location": location,
        "source": site or "unknown",
        "url": url,
        "company_url": safe_url(first(d, "company_url")),
        "posted_date": posted,
        "salary": salary,
        "job_type": clean(first(d, "job_type")),
        "is_remote": clean(first(d, "is_remote")),
        "experience": clean(first(d, "job_level", "experience_level")),
        "description": description[:18000],
        "search_term": search_term,
        "search_location": search_location,
        "collected_at": datetime.now(timezone.utc).isoformat(),
    }

def send_email(jobs, source_status):
    address = os.getenv("GMAIL_ADDRESS", "").strip()
    app_password = os.getenv("GMAIL_APP_PASSWORD", "").replace(" ", "").strip()
    recipient = os.getenv("JOB_SCOUT_RECIPIENT", address).strip()
    if not address or not app_password or not recipient:
        print("EMAIL SKIPPED: Add GitHub Actions secrets GMAIL_ADDRESS and GMAIL_APP_PASSWORD.")
        return
    today = datetime.now().strftime("%d %b %Y")
    msg = EmailMessage()
    msg["Subject"] = f"Procurement Job Scout — {today} — {len(jobs)} listings"
    msg["From"] = address
    msg["To"] = recipient

    lines = [
        f"Procurement Job Scout — {today}",
        f"Listings collected: {len(jobs)}",
        "Coverage attempted: LinkedIn, Indeed, Naukri; India and Punjab searches.",
        "",
        "This is a best-effort collection. Sources can block automated access, and listings may be stale or duplicated.",
        "Always open the original link to verify the vacancy is active before applying.",
        "",
    ]
    for i, job in enumerate(jobs, 1):
        lines.extend([
            f"{i}. {job.get('title') or 'Title not provided'}",
            f"Company: {job.get('company') or 'Not listed'}",
            f"Location: {job.get('location') or 'Not listed'}",
            f"Source: {job.get('source') or 'Unknown'} | Posted: {job.get('posted_date') or 'Not provided'}",
            f"Salary: {job.get('salary') or 'Not listed'}",
            f"Apply/details: {job.get('url') or 'No direct link returned'}",
            "",
        ])
    lines += ["SOURCE STATUS", ""]
    for s in source_status:
        lines.append(f"{s.get('site')} | {s.get('location')} | {s.get('search_term')} | {s.get('status')} | {s.get('count', 0)} jobs")
        if s.get("error"):
            lines.append(f"  Error: {s['error']}")
    msg.set_content("\n".join(lines))
    msg.add_alternative(
        "<html><body><h2>Procurement Job Scout</h2>"
        f"<p><b>{len(jobs)} listings</b> collected. Coverage attempted: LinkedIn, Indeed, Naukri.</p>"
        "<p>Best-effort collection only. Open the original link to verify every vacancy.</p>"
        "<table border='1' cellpadding='6' cellspacing='0'><tr><th>Role</th><th>Company</th><th>Location</th><th>Source</th><th>Posted</th><th>Salary</th><th>Link</th></tr>"
        + "".join(
            "<tr><td>" + html_escape(j.get("title")) + "</td><td>" + html_escape(j.get("company")) +
            "</td><td>" + html_escape(j.get("location")) + "</td><td>" + html_escape(j.get("source")) +
            "</td><td>" + html_escape(j.get("posted_date")) + "</td><td>" + html_escape(j.get("salary")) +
            "</td><td>" + (f"<a href='{html_escape(j.get('url'))}'>Open vacancy</a>" if j.get("url") else "No link") +
            "</td></tr>" for j in jobs[:250]
        ) + "</table><p>For the full consolidated list, open your GitHub Pages dashboard.</p></body></html>",
        subtype="html",
    )
    # Attach CSV so the full list is easy to filter.
    if OUTPUT_CSV.exists():
        msg.add_attachment(OUTPUT_CSV.read_bytes(), maintype="text", subtype="csv", filename="procurement-jobs.csv")
    context = ssl.create_default_context()
    try:
        with smtplib.SMTP("smtp.gmail.com", 587, timeout=30) as server:
            server.ehlo()
            server.starttls(context=context)
            server.ehlo()
            server.login(address, app_password)
            server.send_message(msg)
        print(f"EMAIL SENT: report submitted to Gmail SMTP for {recipient}")
    except Exception as exc:
        print(f"EMAIL ERROR: {type(exc).__name__}: {exc}")
        # Do not hide the collected JSON/CSV just because email failed.

def html_escape(value):
    import html
    return html.escape(clean(value), quote=True)

def main():
    jobs_by_key = {}
    status = []
    print("Starting multi-source procurement job collection.")
    print(f"Sources: {', '.join(SITES)} | Results per search: {RESULTS_PER_SEARCH} | Lookback: {HOURS_OLD} hours")

    for location, location_label in LOCATIONS:
        for term in ROLE_SEARCHES:
            for site in SITES:
                entry = {
                    "site": site,
                    "location": location_label,
                    "search_term": term,
                    "status": "started",
                    "count": 0,
                }
                try:
                    print(f"Searching source={site!r}, role={term!r}, location={location!r}")
                    frame = scrape_jobs(
                        site_name=[site],
                        search_term=term,
                        location=location,
                        results_wanted=RESULTS_PER_SEARCH,
                        hours_old=HOURS_OLD,
                        country_indeed="India",
                        linkedin_fetch_description=True,
                        description_format="markdown",
                        verbose=0,
                    )
                    count = 0
                    if frame is not None and not frame.empty:
                        for _, row in frame.iterrows():
                            job = normalize_row(row, term, location_label)
                            if not job["title"] or not job["url"]:
                                continue
                            key = re.sub(r"[?#].*$", "", job["url"].rstrip("/")).lower()
                            if key not in jobs_by_key:
                                jobs_by_key[key] = job
                            else:
                                old = jobs_by_key[key]
                                if len(job.get("description", "")) > len(old.get("description", "")):
                                    jobs_by_key[key] = {**old, **{k: v for k, v in job.items() if v}}
                            count += 1
                    entry["status"] = "ok" if count else "empty"
                    entry["count"] = count
                except Exception as exc:
                    entry["status"] = "error"
                    entry["error"] = f"{type(exc).__name__}: {str(exc)[:500]}"
                    print(f"SOURCE ERROR: {site}: {entry['error']}")
                status.append(entry)
                time.sleep(2)

    jobs = list(jobs_by_key.values())
    # Punjab-first display; then latest posting date where available.
    def sort_key(job):
        loc = (job.get("location", "") + " " + job.get("search_location", "")).lower()
        punjab = any(x in loc for x in ["punjab", "jalandhar", "ludhiana", "mohali", "chandigarh", "amritsar", "patiala", "bathinda"])
        try:
            posted_ts = datetime.fromisoformat(job.get("posted_date", "").replace("Z", "+00:00")).timestamp()
        except Exception:
            posted_ts = 0
        return (not punjab, -posted_ts)
    jobs.sort(key=sort_key)

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "count": len(jobs),
        "sources_attempted": SITES,
        "locations_attempted": [x[1] for x in LOCATIONS],
        "roles_searched": ROLE_SEARCHES,
        "lookback_hours": HOURS_OLD,
        "disclaimer": "Best-effort search results. Portals may restrict automated access; this is not guaranteed to include every vacancy. Verify the listing on the original site.",
        "jobs": jobs,
    }
    OUTPUT_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    STATUS_JSON.write_text(json.dumps({
        "generated_at": payload["generated_at"],
        "status": status,
        "unique_jobs": len(jobs),
        "success_count": sum(1 for s in status if s["status"] == "ok"),
        "empty_count": sum(1 for s in status if s["status"] == "empty"),
        "error_count": sum(1 for s in status if s["status"] == "error"),
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    # Write a filterable CSV without requiring pandas.
    import csv
    columns = ["title", "company", "location", "source", "posted_date", "salary", "job_type", "experience", "url", "company_url", "search_term", "description"]
    with OUTPUT_CSV.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(jobs)

    print(f"COLLECTION COMPLETE: {len(jobs)} unique listings.")
    print(f"Source status: {sum(1 for s in status if s['status']=='ok')} successful search batches, "
          f"{sum(1 for s in status if s['status']=='empty')} empty, "
          f"{sum(1 for s in status if s['status']=='error')} errors.")
    send_email(jobs, status)

if __name__ == "__main__":
    main()
