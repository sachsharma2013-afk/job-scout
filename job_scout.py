
import os
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
import smtplib
from email.message import EmailMessage
from html import escape

RECIPIENT = os.getenv("TO_EMAIL", "sachin30131@gmail.com")

SEARCHES = [
    '"Procurement Manager" India',
    '"Purchase Manager" India',
    '"Sourcing Manager" India',
    '"Procurement Manager" Punjab India',
    '"Purchase Manager" Punjab India',
    'site:linkedin.com/jobs procurement manager India',
    'site:naukri.com procurement manager India',
    'site:indeed.com procurement manager India',
]

def fetch_jobs(query):
    params = urllib.parse.urlencode({
        "q": query + " when:1d",
        "hl": "en-IN",
        "gl": "IN",
        "ceid": "IN:en",
    })
    url = "https://news.google.com/rss/search?" + params
    request = urllib.request.Request(
        url, headers={"User-Agent": "Mozilla/5.0 JobScout/1.0"}
    )
    with urllib.request.urlopen(request, timeout=25) as response:
        root = ET.fromstring(response.read())

    results = []
    for item in root.findall(".//item"):
        title = item.findtext("title", "").strip()
        link = item.findtext("link", "").strip()
        date = item.findtext("pubDate", "").strip()
        if title and link:
            results.append({
                "title": title,
                "link": link,
                "date": date,
            })
    return results

def main():
    jobs = {}
    errors = []

    for query in SEARCHES:
        try:
            for job in fetch_jobs(query):
                jobs[job["link"]] = job
        except Exception as error:
            errors.append(f"{query}: {error}")

    if not jobs:
        raise RuntimeError(
            "No search results were retrieved. Check the workflow logs."
        )

    message = EmailMessage()
    message["Subject"] = (
        f"Daily Procurement Job Scout: {len(jobs)} search results"
    )
    message["From"] = os.environ["GMAIL_ADDRESS"]
    message["To"] = RECIPIENT

    text_lines = [
        "DAILY PROCUREMENT JOB SCOUT",
        "",
        "Target roles: Procurement Manager, Purchase Manager, "
        "Sourcing Manager",
        "Location: India, with priority for Punjab",
        "",
        "These are search results, not verified vacancies. "
        "Open each link to check details and application status.",
        "",
    ]

    html_items = []
    for job in sorted(
        jobs.values(), key=lambda item: item["title"].lower()
    ):
        text_lines.extend([
            job["title"],
            job["date"],
            job["link"],
            "",
        ])
        html_items.append(
            "<li><a href=\"" + escape(job["link"], quote=True) + "\">"
            + escape(job["title"]) + "</a><br>"
            + escape(job["date"]) + "</li>"
        )

    if errors:
        text_lines.extend(["", "Some searches failed:", *errors])

    message.set_content("\n".join(text_lines))
    message.add_alternative(
        "<h2>Daily Procurement Job Scout</h2>"
        "<p>India-wide search, prioritising Punjab. "
        "Results are unverified; check each listing before applying.</p>"
        "<ul>" + "".join(html_items) + "</ul>",
        subtype="html",
    )

    with smtplib.SMTP("smtp.gmail.com", 587, timeout=30) as server:
        server.starttls()
        server.login(
            os.environ["GMAIL_ADDRESS"],
            os.environ["GMAIL_APP_PASSWORD"],
        )
        server.send_message(message)

    print(f"Email sent to {RECIPIENT}; results: {len(jobs)}")
    if errors:
        print("Search warnings:", errors)

if __name__ == "__main__":
    main()
