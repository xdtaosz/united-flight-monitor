"""SMTP email sender for award flight search results."""

from __future__ import annotations

import smtplib
import ssl
from email.mime.text import MIMEText

from scraper import AwardOffer


def send_results_email(
    to_addr: str,
    origin: str,
    destination: str,
    offers: list[AwardOffer],
    subject: str | None = None,
) -> bool:
    from config import settings

    smtp_user = settings.email_smtp_user or settings.email_from
    if not to_addr or not smtp_user or not settings.email_smtp_password:
        return False

    if subject is None:
        subject = f"Award Alert: {origin.upper()} -> {destination.upper()} - {len(offers)} deal(s)"

    html = _build_html_body(offers, origin, destination, subject)
    return _send_email_raw(
        to_addr=to_addr,
        subject=subject,
        html_body=html,
        from_addr=settings.email_from or smtp_user,
        smtp_host=settings.email_smtp_host,
        smtp_port=settings.email_smtp_port,
        smtp_user=smtp_user,
        smtp_password=settings.email_smtp_password,
    )


def send_summary_email(
    to_addr: str,
    origin: str,
    destination: str,
    start_date: str,
    end_date: str,
    total_dates: int,
    total_offers: int,
) -> bool:
    from config import settings

    smtp_user = settings.email_smtp_user or settings.email_from
    if not to_addr or not smtp_user or not settings.email_smtp_password:
        return False

    subject = f"United Monitor: {origin.upper()} -> {destination.upper()} - No Deals Found"
    body = (
        f"United Flight Monitor - Search Summary\n"
        f"Route: {origin.upper()} -> {destination.upper()}\n"
        f"Date range: {start_date} to {end_date}\n"
        f"Dates searched: {total_dates}\n"
        f"Matching offers: {total_offers}\n\n"
        f"No flights matched your criteria (max miles, excluded airports).\n"
    )
    return _send_email_raw(
        to_addr=to_addr,
        subject=subject,
        html_body=None,
        text_body=body,
        from_addr=settings.email_from or smtp_user,
        smtp_host=settings.email_smtp_host,
        smtp_port=settings.email_smtp_port,
        smtp_user=smtp_user,
        smtp_password=settings.email_smtp_password,
    )


def _build_html_body(
    offers: list[AwardOffer],
    origin: str,
    destination: str,
    subject: str,
) -> str:
    from filters import format_offer_table_rows

    rows = format_offer_table_rows(offers)
    return f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="font-family:Arial,sans-serif;background:#f5f5f5;padding:20px;">
<div style="max-width:800px;margin:0 auto;background:#fff;border-radius:8px;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,.1);">
<div style="background:#1a237e;color:#fff;padding:20px;text-align:center;">
<h2 style="margin:0;">United Award Alert</h2>
<p style="margin:8px 0 0;opacity:.9;">{origin.upper()} -> {destination.upper()}</p>
</div>
<div style="padding:20px;">
<p><strong>{len(offers)} matching award offer(s)</strong> found.</p>
<table style="width:100%;border-collapse:collapse;margin-top:12px;">
<thead>
<tr style="background:#f5f5f5;">
<th style="padding:8px;border-bottom:2px solid #ddd;text-align:center;">Date</th>
<th style="padding:8px;border-bottom:2px solid #ddd;text-align:center;">Stops</th>
<th style="padding:8px;border-bottom:2px solid #ddd;text-align:center;">Duration</th>
<th style="padding:8px;border-bottom:2px solid #ddd;text-align:center;">Cabin</th>
<th style="padding:8px;border-bottom:2px solid #ddd;text-align:center;">Miles</th>
<th style="padding:8px;border-bottom:2px solid #ddd;text-align:center;">Taxes</th>
<th style="padding:8px;border-bottom:2px solid #ddd;text-align:center;">Seats</th>
<th style="padding:8px;border-bottom:2px solid #ddd;text-align:center;">Flight</th>
</tr>
</thead>
<tbody>{rows}
</tbody>
</table>
<p style="margin-top:16px;font-size:12px;color:#888;">Sent by United Flight Monitor</p>
</div>
</div>
</body>
</html>"""


def _send_email_raw(
    to_addr: str,
    subject: str,
    from_addr: str,
    smtp_host: str,
    smtp_port: int,
    smtp_user: str,
    smtp_password: str,
    html_body: str | None = None,
    text_body: str | None = None,
) -> bool:
    try:
        if html_body:
            msg = MIMEText(html_body, "html")
        elif text_body:
            msg = MIMEText(text_body, "plain")
        else:
            return False

        msg["Subject"] = subject
        msg["From"] = from_addr
        msg["To"] = to_addr

        context = ssl.create_default_context()
        with smtplib.SMTP_SSL(smtp_host, smtp_port, context=context, timeout=30) as server:
            server.login(smtp_user, smtp_password)
            to_addrs = [a.strip() for a in to_addr.split(",")]
            server.sendmail(msg["From"], to_addrs, msg.as_string())
        return True
    except Exception:
        return False
