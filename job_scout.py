
def main():
    import json
    import os
    import urllib.request

    recipient = "sachin30131@gmail.com"
    api_key = os.environ["RESEND_API_KEY"]

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

    lines = [
        "Daily Procurement Job Scout",
        "",
        "India-wide search, prioritising Punjab.",
        "Results are unverified; open links to check vacancies.",
        "",
    ]

    for job in sorted(jobs.values(), key=lambda x: x["title"].lower()):
        lines.extend([
            job["title"],
            job["date"],
            job["link"],
            "",
        ])

    if errors:
        lines.extend(["Warnings:", *errors])

    payload = {
        "from": "Job Scout <onboarding@resend.dev>",
        "to": [recipient],
        "subject": f"Procurement Job Scout: {len(jobs)} results",
        "text": "\n".join(lines),
    }

    request = urllib.request.Request(
        "https://api.resend.com/emails",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            result = json.loads(response.read().decode("utf-8"))
            print("Resend accepted email. ID:", result.get("id"))
            print("Search results:", len(jobs))
    except Exception as error:
        print("Email sending failed:", error)
        raise

if __name__ == "__main__":
    main()
