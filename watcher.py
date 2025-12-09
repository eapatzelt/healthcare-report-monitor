import os
import re
import hashlib
import smtplib
from email.mime.text import MIMEText

import requests
from bs4 import BeautifulSoup


# ---------- SOURCES TO MONITOR ----------

# For v1, we keep it simple: we either pick up the latest year mentioned
# on the page, or we hash the page contents.
SOURCES = [
    {
        "id": "cms_nhe",
        "name": "CMS National Health Expenditure Projections",
        "url": "https://www.cms.gov/data-research/statistics-trends-and-reports/national-health-expenditure-data/projected",
        "mode": "latest_year",
        "min_year": 2015,
    },
    {
        "id": "kff_ehbs",
        "name": "KFF Employer Health Benefits Survey",
        "url": "https://www.kff.org/series/employer-health-benefits-survey/",
        "mode": "latest_year",
        "min_year": 2015,
    },
    {
        "id": "trilliant_trends",
        "name": "Trilliant – Health Economy Trends Report",
        # You can swap this for the general reports listing if you want:
        # "url": "https://www.trillianthealth.com/market-research/reports",
        "url": "https://www.trillianthealth.com/market-research/reports/2025-health-economy-trends",
        "mode": "hash",
    },
    {
        "id": "kaufman_flash",
        "name": "Kaufman Hall National Hospital Flash Report",
        "url": "https://www.kaufmanhall.com/insights-reports/national-hospital-flash-report",
        "mode": "kaufman_title",
    },
    {
        "id": "milliman_mmi",
        "name": "Milliman Medical Index",
        "url": "https://www.milliman.com/en/insights/milliman-medical-index-archive",
        "mode": "latest_year",
        "min_year": 2010,
    },
    {
        "id": "hcci_cost_util",
        "name": "HCCI – Health Care Cost and Utilization Report",
        "url": "https://healthcarecostinstitute.org/research/annual-reports",
        "mode": "latest_year",
        "min_year": 2010,
    },
    {
        "id": "fair_health_indicators",
        "name": "FAIR Health – Healthcare Indicators",
        "url": "https://www.fairhealth.org/publications/white-papers",
        "mode": "latest_year",
        "min_year": 2015,
    },
    {
        "id": "bgh_employer_strategy",
        "name": "Business Group on Health – Large Employer Survey",
        "url": "https://www.businessgrouphealth.org/en/topics/employer-survey",
        "mode": "latest_year",
        "min_year": 2015,
    },
    {
        "id": "commonwealth_intl_survey",
        "name": "Commonwealth Fund – International Health Policy Survey",
        "url": "https://www.commonwealthfund.org/international-health-policy-survey",
        "mode": "latest_year",
        "min_year": 2010,
    },
    {
        "id": "deloitte_us_outlook",
        "name": "Deloitte – US Health Care Outlook",
        "url": "https://www2.deloitte.com/us/en/pages/life-sciences-and-health-care/articles/us-health-care-industry-outlook.html",
        "mode": "latest_year",
        "min_year": 2015,
    },
    {
        "id": "pwc_top_issues",
        "name": "PwC – Top Health Industry Issues",
        "url": "https://www.pwc.com/us/en/industries/health-industries/library/top-health-industry-issues.html",
        "mode": "latest_year",
        "min_year": 2015,
    },
    {
        "id": "aha_fast_facts",
        "name": "AHA – Fast Facts on U.S. Hospitals",
        "url": "https://www.aha.org/statistics/fast-facts-us-hospitals",
        "mode": "latest_year",
        "min_year": 2010,
    },
    {
        "id": "rand_hospital_prices",
        "name": "RAND – Hospital Price Transparency Studies",
        "url": "https://www.rand.org/health-care/projects/hospital-price-transparency.html",
        "mode": "latest_year",
        "min_year": 2010,
    },
]


# ---------- EMAIL CONFIG FROM ENV VARS ----------

SMTP_HOST = os.environ.get("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USER = os.environ.get("SMTP_USER", "")
SMTP_PASS = os.environ.get("SMTP_PASS", "")
EMAIL_FROM = os.environ.get("EMAIL_FROM", "")
EMAIL_TO = os.environ.get("EMAIL_TO", "")


# ---------- HELPERS ----------

def fetch_html(url: str) -> str:
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    return resp.text


def extract_latest_year(html: str, min_year: int = 2010) -> str | None:
    # Grab all 4-digit years from 2000–2049, then take the max >= min_year
    years = set(int(y) for y in re.findall(r"(20[0-4]\d)", html))
    years = [y for y in years if y >= min_year]
    return str(max(years)) if years else None


def hash_page(html: str) -> str:
    return hashlib.sha256(html.encode("utf-8")).hexdigest()[:10]


def extract_kaufman_title(html: str) -> str | None:
    soup = BeautifulSoup(html, "html.parser")
    h1 = soup.find("h1")
    if not h1:
        return None
    text = " ".join(h1.get_text(strip=True).split())
    return text or None


def get_version_for_source(src: dict) -> str:
    html = fetch_html(src["url"])
    mode = src.get("mode", "hash")

    if mode == "latest_year":
        year = extract_latest_year(html, src.get("min_year", 2010))
        return year or "unknown-year"
    elif mode == "kaufman_title":
        label = extract_kaufman_title(html)
        return label or hash_page(html)
    elif mode == "hash":
        return hash_page(html)
    else:
        # Default to hash if we don't recognize the mode
        return hash_page(html)


def send_email(subject: str, body: str) -> None:
    if not (SMTP_USER and SMTP_PASS and EMAIL_FROM and EMAIL_TO):
        # Email not configured; just print for debugging.
        print("Email settings not fully configured. Here's what would be sent:")
        print("SUBJECT:", subject)
        print(body)
        return

    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = EMAIL_FROM
    msg["To"] = EMAIL_TO

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
        server.starttls()
        server.login(SMTP_USER, SMTP_PASS)
        server.send_message(msg)


def run():
    lines = []
    errors = []

    for src in SOURCES:
        sid = src["id"]
        name = src["name"]
        url = src["url"]
        try:
            version = get_version_for_source(src)
            lines.append(f"- {name}: {version}  ({url})")
            print(f"[OK] {sid}: {version}")
        except Exception as e:
            msg = f"[ERROR] {sid}: {e}"
            print(msg)
            errors.append(msg)

    if not lines and errors:
        # Everything failed – send a failure email
        subject = "Healthcare report watcher: ALL CHECKS FAILED"
        body = "All sources failed to fetch:\n\n" + "\n".join(errors)
        send_email(subject, body)
        return

    subject = "Healthcare report watcher: latest snapshot"
    body = "Here is the latest snapshot of monitored healthcare reports:\n\n"
    body += "\n".join(lines)

    if errors:
        body += "\n\nErrors:\n" + "\n".join(errors)

    send_email(subject, body)


if __name__ == "__main__":
    run()
