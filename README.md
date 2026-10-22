# Procurement Job Scout — consolidated dashboard

A GitHub Actions job collector and GitHub Pages dashboard for Procurement Manager, Purchase Manager, Sourcing Manager and related roles. It attempts LinkedIn, Indeed, Naukri and Glassdoor searches for India and Punjab, consolidates duplicate links, saves JSON/CSV, exposes per-search diagnostics, and optionally emails a daily digest.

## Important limitation

This is a **best-effort personal job-search helper**, not a guarantee of every open vacancy. Job portals change their pages and may restrict automated access. Follow each portal's terms and use the original listing to verify that the job is active. A source error is recorded in `data/source_status.json`; an empty result does not necessarily mean there are no vacancies.

## Install / replace your existing repository files

Upload these files to the root of your existing `job-scout` repository, preserving the `.github/workflows/job-scout.yml` path:

- `index.html`
- `job_scout.py`
- `requirements.txt`
- `.github/workflows/job-scout.yml`
- `data/jobs.json`
- `data/jobs.csv`
- `data/source_status.json`

The included `data` files are starter placeholders. The first successful workflow run replaces them.

## GitHub setup

1. Open the repository → **Settings → Pages**.
2. Set **Build and deployment** to **Deploy from a branch**.
3. Select branch `main` and folder `/ (root)`, then Save.
4. Open **Actions → Daily Procurement Job Scout → Run workflow** for the first run.
5. After it completes, open the Pages URL. The dashboard loads `data/jobs.json` and links to each original listing.
6. Workflow runs daily at **08:00 India Standard Time** (02:30 UTC).

The workflow needs `contents: write` to commit refreshed JSON/CSV back to the repository. If branch protection prevents Actions from pushing, change repository settings or use artifacts instead.

## Optional Gmail delivery

The dashboard and CSV do not need email credentials. To enable a daily email, configure these in **Settings → Secrets and variables → Actions → New repository secret**:

- `GMAIL_ADDRESS`: the Gmail account that will send the message.
- `GMAIL_APP_PASSWORD`: a Google App Password for that account (not your normal Gmail password).
- `JOB_SCOUT_RECIPIENT`: optional; if omitted, the report is sent to `GMAIL_ADDRESS`.

Google generally requires 2-Step Verification before you can create an App Password. If you cannot create one, leave the secrets unset: the job collection/dashboard still runs, and the log says email was skipped. Never paste secrets into code or chat. The old `RESEND_API_KEY` is not used by this rebuild.

## Tuning coverage

Edit `ROLE_SEARCHES`, `LOCATIONS`, and `SITES` near the top of `job_scout.py`. Increase `RESULTS_PER_SEARCH` or `HOURS_OLD` via the workflow environment if desired. More queries take longer and can trigger rate limits. Current defaults search the last 7 days and include related procurement/supply-chain titles so you can review a broad list without an automatic resume-score cutoff.

## Files

- `data/jobs.json`: dashboard data
- `data/jobs.csv`: downloadable spreadsheet-friendly results
- `data/source_status.json`: counts and error messages by search batch
- `index.html`: searchable consolidated dashboard

## Troubleshooting

- If Actions fails at dependency installation, open the failed step and check whether `python-jobspy` currently supports the Python version in the workflow.
- If a portal returns errors/blocks, open the `View source diagnostics` link on the dashboard. That portal may need a different integration; don't interpret a source error as zero vacancies.
- If jobs are collected but no email arrives, check the log for `EMAIL SENT`, `EMAIL SKIPPED`, or `EMAIL ERROR`. The dashboard and CSV are still generated if email fails.
- GitHub Pages may take a few minutes to publish after the first setup or commit.
