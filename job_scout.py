
import json
import os
import urllib.parse
import urllib.request
import urllib.error
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

# --------------------------------------------------
# JOB SCOUT CONFIGURATION
# --------------------------------------------------

RECIPIENT = "sachin30131@gmail.com"
RESEND_API_URL = "https://api.resend.com/emails"
RESEND_SENDER = "Job Scout <onboarding@resend.dev>"

SEARCHES = [
    '"Procurement Manager" India',
    '"Purchase Manager" India',
    '"Sourcing Manager" India',
    '"Procurement Manager" Punjab India',
    '"Purchase Manager" Punjab India',
    '"Sourcing Manager" Punjab India',
    'site:linkedin.com/jobs procurement manager India',
    'site:naukri.com procurement manager India',
    'site:indeed.com procurement manager India',
]

# --------------------------------------------------
# FETCH SEARCH RESULTS FROM GOOGLE NEWS RSS
# --------------------------------------------------

def fetch_jobs(query):
    params = urllib.parse.urlencode({
        "q": query + " when:1d",
        "hl": "en-IN",
        "gl": "IN",
        "ceid": "IN:en",
    })

    url = "https://news.google.com/rss/search?" + params

    request = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0 JobScout/1.0"},
    )

    with urllib.request.urlopen(request, timeout=30) as response:
        root = ET.fromstring(response.read())

    results = []

    for item in root.findall(".//item"):
        title = item.findtext("title", "").strip()
        link = item.findtext("link", "").strip()
        published = item.findtext("pubDate", "").strip()
        description = item.findtext("description", "").strip()

        if title and link:
            results.append({
                "title": title,
                "link": link,
                "date": published,
                "description": description,
                "query": query,
            })

    return results


# --------------------------------------------------
# BASIC KEYWORD SCREENING
# --------------------------------------------------

def estimate_match(job):
    """
    Preliminary keyword score, NOT a genuine resume match.
    Replace with proper resume/job-description comparison later.
    """

    text = (
        job["title"] + " " + job["description"]
    ).lower()

    role_terms = [
        "procurement",
        "purchase",
        "sourcing",
        "buyer",
        "supply chain",
    ]

    skill_terms = [
        "vendor",
        "negotiation",
        "rfq",
        "tender",
        "sap",
        "mro",
        "capex",
        "contract",
        "manufacturing",
    ]

    role_hits = sum(term in text for term in role_terms)
    skill_hits = sum(term in text for term in skill_terms)

    # Transparent preliminary score out of 100.
    score = min(100, role_hits * 12 + skill_hits * 7)

    return score


# --------------------------------------------------
# CREATE EMAIL CONTENT
# --------------------------------------------------

def build_email(jobs, errors):
    now = datetime.now(timezone.utc).strftime("%d %b %Y, %H:%M UTC")

    lines = [
        "DAILY PROCUREMENT JOB SCOUT",
        f"Generated: {now}",
        "",
        "Target roles: Procurement Manager, Purchase Manager, "
        "Sourcing Manager",
        "Location: India, prioritising Punjab",
        "",
        "IMPORTANT:",
        "These are Google News RSS search results, not verified vacancies.",
        "The score below is a preliminary keyword score, NOT a resume match.",
        "",
    ]

    for index, job in enumerate(
        sorted(jobs.values(), key=lambda item: item["score"], reverse=True),
        start=1,
    ):
        lines.extend([
            f"{index}. {job['title']}",
            f"Preliminary keyword score: {job['score']}%",
            f"Published: {job['date'] or 'Not provided'}",
            f"Search: {job['query']}",
            f"Link: {job['link']}",
            "",
        ])

    if not jobs:
        lines.extend([
            "No search results were collected today.",
            "",
        ])

    if errors:
        lines.extend([
            "SEARCH WARNINGS",
            *errors,
            "",
        ])

    lines.extend([
        "This email does not guarantee that a vacancy is active.",
        "Open each result and confirm the job details before applying.",
    ])

    return "\n".join(lines)


# --------------------------------------------------
# SEND EMAIL THROUGH RESEND
# --------------------------------------------------

def send_email(subject, body):
    api_key = os.environ.get("RESEND_API_KEY")

    if not api_key:
        raise RuntimeError(
            "RESEND_API_KEY is missing. Add it in GitHub Actions Secrets "
            "and expose it to the workflow step."
        )

    payload = {
        "from": RESEND_SENDER,
        "to": [RECIPIENT],
        "subject": subject,
        "text": body,
    }

    request = urllib.request.Request(
        RESEND_API_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            response_body = response.read().decode("utf-8")
            result = json.loads(response_body)

            print("Resend accepted the email request.")
            print("Email ID:", result.get("id", "Not returned"))
            print("Recipient:", RECIPIENT)

    except urllib.error.HTTPError as error:
        details = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(
            f"Resend returned HTTP {error.code}: {details}"
        ) from error

    except urllib.error.URLError as error:
        raise RuntimeError(
            f"Could not connect to Resend: {error.reason}"
        ) from error


# --------------------------------------------------
# MAIN JOB
# --------------------------------------------------

def main():
    jobs = {}
    errors = []

    print("Starting daily Procurement Job Scout...")

    for query in SEARCHES:
        print(f"Searching: {query}")

        try:
            results = fetch_jobs(query)

            for job in results:
                job["score"] = estimate_match(job)

                # Deduplicate results by URL.
                if job["link"] not in jobs:
                    jobs[job["link"]] = job

        except Exception as error:
            warning = f"{query}: {type(error).__name__}: {error}"
            errors.append(warning)
            print("Search warning:", warning)

    print(f"Unique results collected: {len(jobs)}")

    if not jobs:
        raise RuntimeError(
            "No search results were retrieved. No email was sent. "
            "Check the search warnings in the workflow log."
        )

    body = build_email(jobs, errors)

    today = datetime.now(timezone.utc).strftime("%d %b %Y")

    send_email(
        subject=f"Daily Procurement Job Scout - {today} ({len(jobs)} results)",
        body=body,
    )

    print("Job Scout finished.")


if __name__ == "__main__":
    main()
