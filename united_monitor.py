"""United Flight Monitor - Main Entry Point.

Orchestrates: login -> search -> filter -> log -> email.
Run: python united_monitor.py
Cron: python united_monitor.py >> ~/.united_monitor/cron.log 2>&1
"""

from __future__ import annotations

import asyncio
import logging
import sys
from datetime import date, datetime
from pathlib import Path

from config import settings


def setup_logging() -> logging.Logger:
    log_dir = settings.logs_dir
    log_file = log_dir / f"united_monitor_{date.today().strftime('%Y%m%d')}.log"

    logger = logging.getLogger("united_monitor")
    logger.setLevel(logging.INFO)

    if not logger.handlers:
        fh = logging.FileHandler(str(log_file))
        fh.setLevel(logging.INFO)
        formatter = logging.Formatter("%(asctime)s %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
        fh.setFormatter(formatter)
        logger.addHandler(fh)

        ch = logging.StreamHandler(sys.stdout)
        ch.setLevel(logging.INFO)
        ch.setFormatter(formatter)
        logger.addHandler(ch)

    return logger


async def main() -> None:
    logger = setup_logging()

    logger.info("=" * 60)
    logger.info("United Flight Monitor starting")
    logger.info(f"  Route: {settings.search_origin} -> {settings.search_destination}")
    logger.info(f"  Cabin: {settings.search_cabin}")
    logger.info(f"  Max miles: {settings.max_miles:,}")
    logger.info(f"  Exclude airports: {settings.exclude_airports_list}")
    logger.info(f"  Date range: {settings.search_start_date} to {settings.search_end_date}")
    logger.info(f"  Rate limit: {settings.search_delay_seconds}s between queries")
    logger.info("=" * 60)

    # Login
    from scraper import UnitedScraper, LoginError
    scraper = UnitedScraper()
    try:
        logged_in = await scraper.login()
        if logged_in:
            logger.info("Login successful (session reused or fresh login)")
        else:
            logger.error("Login failed")
            await scraper.close()
            return
    except LoginError as e:
        logger.error(f"Login error: {e}")
        await scraper.close()
        return

    # Parse dates
    try:
        start_date = date.fromisoformat(settings.search_start_date) if settings.search_start_date else date.today()
        end_date = date.fromisoformat(settings.search_end_date) if settings.search_end_date else start_date
    except ValueError as e:
        logger.error(f"Invalid date format: {e}")
        await scraper.close()
        return

    total_days = (end_date - start_date).days + 1
    logger.info(f"Searching {total_days} days from {start_date} to {end_date}")

    # Search
    try:
        raw_offers = await scraper.search_range(
            origin=settings.search_origin,
            destination=settings.search_destination,
            start_date=start_date,
            end_date=end_date,
            cabin=settings.search_cabin,
            max_miles=settings.max_miles,
        )
    except Exception as e:
        logger.error(f"Search failed: {e}")
        await scraper.close()
        return
    finally:
        await scraper.close()

    logger.info(f"Raw results: {len(raw_offers)} offers across all dates")

    # Filter
    from filters import filter_offers
    filtered = filter_offers(raw_offers, settings.max_miles, settings.exclude_airports_list)
    excluded_count = len(raw_offers) - len(filtered)
    logger.info(f"Filtered: {len(filtered)} matching, {excluded_count} excluded (MNL/miles)")

    # Log filtered results
    if filtered:
        from filters import format_offer_summary
        logger.info("Matching flights:\n" + format_offer_summary(filtered[:50]))
        if len(filtered) > 50:
            logger.info(f"  ... and {len(filtered) - 50} more")
    else:
        logger.info("No flights matched the filter criteria.")

    # Email
    if settings.email_to:
        try:
            from emailer import send_results_email, send_summary_email

            if filtered:
                ok = send_results_email(
                    to_addr=settings.email_to,
                    origin=settings.search_origin,
                    destination=settings.search_destination,
                    offers=filtered,
                )
                if ok:
                    logger.info(f"Email sent to {settings.email_to} with {len(filtered)} offers")
                else:
                    logger.error("Email send failed")
            else:
                ok = send_summary_email(
                    to_addr=settings.email_to,
                    origin=settings.search_origin,
                    destination=settings.search_destination,
                    start_date=str(start_date),
                    end_date=str(end_date),
                    total_dates=total_days,
                    total_offers=len(raw_offers),
                )
                if ok:
                    logger.info(f"Summary email sent to {settings.email_to}")
                else:
                    logger.error("Summary email send failed")
        except Exception as e:
            logger.error(f"Email error: {e}")
    else:
        logger.info("EMAIL_TO not configured, skipping email notification")

    logger.info("=" * 60)
    logger.info(f"United Flight Monitor complete: {len(filtered)} matching / {len(raw_offers)} total")
    logger.info("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
