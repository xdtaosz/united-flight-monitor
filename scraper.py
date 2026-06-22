"""United Airlines award flight search scraper.

Handles:
  - Browser login with cookie/session persistence
  - MFA challenge (interactive prompt on first run)
  - Award calendar scan (FetchAwardCalendar)
  - Detailed flight search (FetchFlights)
  - Response parsing into structured data
"""

from __future__ import annotations

import asyncio
import json
import random
import urllib.parse
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from playwright.async_api import BrowserContext, Page, async_playwright

UNITED_BASE = "https://www.united.com"
UNITED_LOGIN = f"{UNITED_BASE}/en/us/login"
UNITED_FSR = f"{UNITED_BASE}/en/us/fsr/choose-flights"


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class FlightSegment:
    airline: str = ""
    flight_number: str = ""
    departure_airport: str = ""
    arrival_airport: str = ""
    departure_time: str = ""
    arrival_time: str = ""
    duration_minutes: int = 0
    aircraft: str = ""
    fare_class: str = ""


@dataclass
class AwardOffer:
    depart_date: str = ""
    miles_required: int = 0
    taxes_fees: float = 0.0
    stops: int = 0
    cabin: str = "economy"
    total_seats_available: int = 0
    total_duration_minutes: int = 0
    segments: list[FlightSegment] = field(default_factory=list)
    source_airline: str = "united"
    query_origin: str = ""
    query_destination: str = ""


# ---------------------------------------------------------------------------
# United Scraper
# ---------------------------------------------------------------------------

class LoginError(Exception):
    pass


class MFARequired(Exception):
    pass


class RateLimitError(Exception):
    pass


import shutil
import sys
from pathlib import Path


def _find_chrome() -> str | None:
    """Auto-detect system Chrome/Chromium executable."""
    for p in (
        "/usr/bin/google-chrome-stable",
        "/usr/bin/google-chrome",
        "/usr/bin/chromium",
        "/usr/bin/chromium-browser",
        "/snap/bin/chromium",
    ):
        if Path(p).is_file():
            return p
    return shutil.which("google-chrome-stable") or shutil.which("google-chrome") or shutil.which("chromium")


class UnitedScraper:
    def __init__(self):
        from config import settings

        self._settings = settings
        self._playwright = None
        self._context: BrowserContext | None = None
        self._bearer_token: str | None = None

        self._session = None
        from session import SessionManager
        self._session = SessionManager()

    @property
    def cookie_file(self) -> Path:
        return self._settings.data_path / "cookies" / "united_cookies.json"

    @property
    def bearer_token(self) -> str | None:
        return self._bearer_token

    # --- Login ---

    async def login(self) -> bool:
        # 1. Try saved session
        data = self._session.load("united")
        if data and data.get("bearer_token"):
            self._bearer_token = data["bearer_token"]
            self._session.touch("united")
            return True

        # 2. Try cookie-based login
        if await self._try_cookie_login():
            return True

        # 3. Full login
        return await self._do_login()

    async def _try_cookie_login(self) -> bool:
        if not self.cookie_file.exists():
            return False
        ctx = await self._ensure_browser()
        cookies = json.loads(self.cookie_file.read_text())
        await ctx.add_cookies(cookies)
        page = await ctx.new_page()
        try:
            await page.goto(UNITED_BASE + "/en/us/", wait_until="commit", timeout=30000)
            await asyncio.sleep(3)
            if await self._is_logged_in(page):
                self._bearer_token = await self._capture_bearer_token(ctx)
                if self._bearer_token:
                    await self._save_full_session()
                await page.close()
                return True
        except Exception:
            pass
        await page.close()
        return False

    async def _do_login(self) -> bool:
        mp_number = self._settings.united_mp_number
        password = self._settings.united_password
        if not mp_number or not password:
            raise LoginError("UNITED_MP_NUMBER and UNITED_PASSWORD must be set in .env")

        ctx = await self._ensure_browser()
        page = await ctx.new_page()
        page.set_default_timeout(self._settings.browser_timeout_ms)
        ddir = self._settings.data_path / "debug"
        ddir.mkdir(parents=True, exist_ok=True)

        try:
            print(f"[DEBUG] Navigating to login page...")
            await page.goto(UNITED_BASE + "/en/us/login", wait_until="load", timeout=60000)
            await asyncio.sleep(5)
            await page.screenshot(path=str(ddir / "01_login_page.png"))
            print(f"[DEBUG] Login page URL: {page.url}")
            print(f"[DEBUG] Page title: {await page.title()}")

            # Dump all visible buttons and inputs
            btns = page.locator("button:visible")
            btn_count = await btns.count()
            print(f"[DEBUG] Visible buttons: {btn_count}")
            for i in range(min(btn_count, 10)):
                txt = await btns.nth(i).text_content()
                print(f"[DEBUG]   button[{i}]: {txt.strip() if txt else '(no text)'}")

            inputs = page.locator("input:visible")
            inp_count = await inputs.count()
            print(f"[DEBUG] Visible inputs: {inp_count}")
            for i in range(min(inp_count, 10)):
                name = await inputs.nth(i).get_attribute("name") or ""
                typ = await inputs.nth(i).get_attribute("type") or ""
                pid = await inputs.nth(i).get_attribute("id") or ""
                print(f"[DEBUG]   input[{i}]: name={name} type={typ} id={pid}")

            # Click Sign in button
            print(f"[DEBUG] Looking for Sign in button...")
            clicked = False
            for selector in ['button:has-text("Sign in")', 'button:has-text("Sign In")']:
                btn = page.locator(selector).first
                c = await btn.count()
                print(f"[DEBUG]   selector '{selector}': count={c}")
                if c > 0:
                    v = await btn.is_visible()
                    print(f"[DEBUG]   visible={v}")
                    if v:
                        await btn.click()
                        await asyncio.sleep(3)
                        clicked = True
                        break
            if not clicked:
                print("[DEBUG] Sign in button not found, trying page content...")
                await page.screenshot(path=str(ddir / "02_no_signin.png"))

            await page.screenshot(path=str(ddir / "02_after_signin_click.png"))

            # Fill MP number
            print(f"[DEBUG] Looking for MP number / email field...")
            mp_field = page.locator(
                'input[name*="MPID"], input[name*="MileagePlus"], '
                'input[name*="mpNumber"], input[name*="email"], '
                'input[id*="email"], input[type="email"]'
            ).first
            mp_count = await mp_field.count()
            mp_visible = mp_count > 0 and await mp_field.is_visible() if mp_count > 0 else False
            print(f"[DEBUG] MP field: count={mp_count} visible={mp_visible}")
            if mp_visible:
                await mp_field.fill(mp_number)
                await asyncio.sleep(1)
                await page.screenshot(path=str(ddir / "03_mp_filled.png"))
                await mp_field.press("Enter")
                await asyncio.sleep(3)

            # Click Continue/Next — aggressive multi-method
            print(f"[DEBUG] Looking for Continue/Next button (aggressive)...");
            continued = False;
            for btn_text in ["Continue", "Next", "Sign in"]:
                for sel in [
                    f'button:has-text("{btn_text}")',
                    f'a:has-text("{btn_text}")',
                    f'[role="button"]:has-text("{btn_text}")',
                    f'span:has-text("{btn_text}")',
                ]:
                    btn = page.locator(sel).first;
                    c = await btn.count();
                    print(f"[DEBUG]   sel={sel}: count={c}");
                    if c > 0:
                        try:
                            await btn.click(timeout=5000);
                        except Exception:
                            try:
                                await btn.click(force=True, timeout=5000);
                            except Exception as e2:
                                print(f"[DEBUG]   click failed: {e2}");
                                continue;
                        await asyncio.sleep(3);
                        continued = True;
                        break;
                if continued:
                    break;
            if not continued:
                print("[DEBUG] Trying JS click on any Continue...");
                try:
                    await page.evaluate('document.querySelector("[class*=continue], [id*=continue], button")?.click()');
                    await asyncio.sleep(3);
                except Exception as e:
                    print(f"[DEBUG] JS click failed: {e}");
            print(f"[DEBUG] Continue clicked: {continued}")

            # Find and dump all inputs again
            print(f"[DEBUG] Looking for password field...")
            all_inputs = page.locator("input:visible")
            inp_count = await all_inputs.count()
            print(f"[DEBUG] Visible inputs now: {inp_count}")
            pw_input = None
            for i in range(inp_count):
                inp = all_inputs.nth(i)
                name = await inp.get_attribute("name") or ""
                typ = await inp.get_attribute("type") or ""
                pid = await inp.get_attribute("id") or ""
                ph = await inp.get_attribute("placeholder") or ""
                print(f"[DEBUG]   input[{i}]: name={name} type={typ} id={pid} placeholder={ph}")
                if typ == "password":
                    pw_input = inp
                    break

            if pw_input is None:
                print(f"[DEBUG] No password input found with type=password")
                # Try any visible input as fallback
                pw_input = page.locator('input[type="password"]').first
                c2 = await pw_input.count()
                print(f"[DEBUG] input[type=password].first count={c2}")

            pw_count = await pw_input.count() if pw_input else 0
            if pw_count == 0:
                await page.screenshot(path=str(ddir / "05_no_password.png"))
                raise LoginError("Cannot find password field")

            await pw_input.wait_for(state="visible", timeout=20000)
            await pw_input.fill(password)
            await asyncio.sleep(1)
            await page.screenshot(path=str(ddir / "05_pw_filled.png"))

            # Click Sign in (final)
            print(f"[DEBUG] Looking for final Sign in button...")
            submit = page.locator('button:has-text("Sign in")').last
            s_count = await submit.count()
            print(f"[DEBUG] Sign in (last): count={s_count}")
            if s_count > 0:
                await submit.click()
                await asyncio.sleep(5)

            await page.screenshot(path=str(ddir / "06_after_login.png"))

            # Handle MFA
            print(f"[DEBUG] Checking for MFA...")
            if await self._detect_mfa(page):
                print(f"[DEBUG] MFA detected, prompting...")
                code = input("Enter MFA verification code: ").strip()
                if code:
                    await self._submit_mfa(page, code)
                    await asyncio.sleep(3)

            await page.screenshot(path=str(ddir / "07_after_mfa.png"))

            logged_in = await self._is_logged_in(page)
            print(f"[DEBUG] Logged in: {logged_in}")
            if not logged_in:
                raise LoginError("Login failed - check credentials or MFA")

            await self._save_cookies()
            self._bearer_token = await self._capture_bearer_token(ctx)
            if self._bearer_token:
                await self._save_full_session()
            print(f"[DEBUG] Login successful")
            return True

        finally:
            await page.close()

    async def _is_logged_in(self, page: Page) -> bool:
        try:
            await page.goto(UNITED_BASE + "/en/us/", wait_until="commit", timeout=30000)
            await asyncio.sleep(3)
            content = await page.content()
            return "Cardmember" in content or '"isLoggedIn":true' in content
        except Exception:
            return False

    async def _detect_mfa(self, page: Page) -> bool:
        content = await page.content()
        indicators = [
            "verification code", "two-factor", "multi-factor",
            "sms code", "security code", "verify your identity", "mfa",
        ]
        return any(ind in content.lower() for ind in indicators)

    async def _submit_mfa(self, page: Page, code: str) -> None:
        mfa_sel = (
            'input[name="otp"], input[autocomplete="one-time-code"], '
            'input[id*="code"]:visible, input[id*="otp"]:visible, '
            'input[type="text"]:visible, input[type="tel"]:visible'
        )
        try:
            mfa_input = await page.wait_for_selector(mfa_sel, timeout=30000)
            if mfa_input:
                await mfa_input.fill(code)
                submit_btn = await page.wait_for_selector(
                    'button[type="submit"]:not([disabled]), '
                    'button:has-text("Verify"):visible, '
                    'button:has-text("Submit"):visible',
                    timeout=15000,
                )
                if submit_btn:
                    await submit_btn.click()
                    await asyncio.sleep(3)
        except Exception:
            pass

    # --- Cookie persistence ---

    async def _save_cookies(self) -> None:
        ctx = await self._ensure_browser()
        cookies = await ctx.cookies()
        self.cookie_file.parent.mkdir(parents=True, exist_ok=True)
        self.cookie_file.write_text(json.dumps(cookies, indent=2))

    async def _save_full_session(self) -> None:
        ctx = await self._ensure_browser()
        pw_cookies = await ctx.cookies()
        self._session.save(
            airline="united",
            cookies=[
                {"name": c["name"], "value": c["value"], "domain": c["domain"],
                 "path": c["path"], "httpOnly": c.get("httpOnly", False),
                 "secure": c.get("secure", False), "sameSite": c.get("sameSite", "Lax")}
                for c in pw_cookies
            ],
            bearer_token=self._bearer_token or "",
        )

    # --- Bearer token capture ---

    async def _capture_bearer_token(self, ctx: BrowserContext) -> str | None:
        captured: list[str] = []

        async def on_request(request):
            nonlocal captured
            if captured:
                return
            url = request.url
            if "FetchAwardCalendar" in url or "FetchFlights" in url:
                raw = request.headers.get("x-authorization-api", "")
                if raw.lower().startswith("bearer "):
                    token = raw[7:].strip()
                    if token:
                        captured.append(token)

        page = await ctx.new_page()
        page.on("request", on_request)
        try:
            search_url = f"{UNITED_FSR}?f=SFO&t=ORD&d={date.today().strftime('%Y/%m/%d')}&tt=1&at=1&sc=3&act=2&px=1&tqp=A"
            await page.goto(search_url, wait_until="commit", timeout=60000)
            await asyncio.sleep(5)
        except Exception:
            pass
        finally:
            page.remove_listener("request", on_request)
            await page.close()

        return captured[0] if captured else None

    # --- Search ---

    async def search_range(
        self,
        origin: str,
        destination: str,
        start_date: date,
        end_date: date,
        cabin: str = "business",
        max_miles: int | None = None,
    ) -> list[AwardOffer]:
        if not await self.login():
            raise LoginError("Cannot search without successful login")

        all_offers: list[AwardOffer] = []
        current = start_date
        while current <= end_date:
            try:
                offers = await self._search_single_date(origin, destination, current, cabin)
                all_offers.extend(offers)
            except RateLimitError:
                break
            except Exception as e:
                print(f"  Error on {current}: {e}")

            current += timedelta(days=1)
            if current <= end_date:
                delay = self._settings.search_delay_seconds
                jitter = random.uniform(0, delay * 0.5)
                await asyncio.sleep(delay + jitter)

        return all_offers

    async def _search_single_date(
        self, origin: str, destination: str, depart_date: date, cabin: str
    ) -> list[AwardOffer]:
        ctx = await self._ensure_browser()
        if self.cookie_file.exists():
            cookies = json.loads(self.cookie_file.read_text())
            await ctx.add_cookies(cookies)

        page = await ctx.new_page()
        page.set_default_timeout(self._settings.browser_timeout_ms)

        search_url = self._build_search_url(origin, destination, depart_date, cabin)
        await page.goto(search_url, wait_until="commit", timeout=60000)
        await asyncio.sleep(5)

        # Auto-fill password if login modal appears
        pw = page.locator('input[type="password"]').first
        if await pw.count() > 0 and await pw.is_visible():
            await pw.fill(self._settings.united_password or "")
            signin = page.locator('button:has-text("Sign in")').last
            if await signin.count() > 0:
                await signin.click()
                await asyncio.sleep(5)
                await page.goto(search_url, wait_until="commit", timeout=60000)
                await asyncio.sleep(5)

        # Execute FetchFlights via JS
        try:
            payload = self._build_api_payload(origin, destination, depart_date, cabin)
            payload_json = json.dumps(payload)
            data = await page.evaluate(
                f"async () => {{ const r = await fetch('/api/flight/FetchFlights',"
                f"{{method:'POST',credentials:'include',headers:{{'Content-Type':'application/json'}},"
                f"body:'{payload_json}'}}); return await r.json(); }}"
            )
        except Exception:
            await page.close()
            return []

        offers = self._parse_flights_response(data, origin, destination)
        await page.close()
        return offers

    def _build_search_url(self, origin: str, destination: str, d: date, cabin: str) -> str:
        sc = "7" if cabin in ("business", "first") else "3"
        params = {
            "f": origin.upper(),
            "t": destination.upper(),
            "d": d.strftime("%Y/%m/%d"),
            "tt": "1",
            "at": "1",
            "sc": sc,
            "act": "2",
            "px": "1",
            "tqp": "A",
        }
        return f"{UNITED_FSR}?{urllib.parse.urlencode(params)}"

    def _build_api_payload(
        self, origin: str, destination: str, d: date, cabin: str
    ) -> dict[str, Any]:
        is_business = cabin in ("business", "first")
        fare_family = "BUSINESS" if is_business else "ECO"
        cabin_main = "premium" if is_business else "eco"
        return {
            "SearchTypeSelection": 1,
            "SortType": "bestmatches",
            "Trips": [{
                "Origin": origin.upper(),
                "Destination": destination.upper(),
                "DepartDate": d.strftime("%Y/%m/%d"),
                "Index": 1,
                "TripIndex": 1,
                "SearchRadiusMilesOrigin": 0,
                "SearchRadiusMilesDestination": 0,
                "DepartTimeApprox": 0,
                "SearchFiltersIn": {
                    "FareFamily": fare_family,
                    "AirportsStop": None,
                    "AirportsStopToAvoid": None,
                    "ShopIndicators": {
                        "IsTravelCreditsApplied": False,
                        "IsDoveFlow": True,
                    },
                },
            }],
            "CabinPreferenceMain": cabin_main,
            "PaxInfoList": [{"PaxType": 1}],
            "AwardTravel": True,
            "NGRP": True,
            "CalendarLengthOfStay": -1,
            "PetCount": 0,
            "FareType": "mixedtoggle",
            "BuildHashValue": "true",
        }

    # --- Response parsing ---

    def _parse_flights_response(
        self, data: dict[str, Any], origin: str, destination: str
    ) -> list[AwardOffer]:
        offers: list[AwardOffer] = []
        d = data.get("data", data)
        for trip in d.get("Trips", []):
            depart_date = trip.get("DepartDate", "")
            for flight in trip.get("Flights", []):
                products = flight.get("Products") or flight.get("Fares") or []
                segments = self._parse_flight_segments(flight)
                for prod in products:
                    ctx = prod.get("Context", {})
                    pax_prices = ctx.get("PaxPrices", [])
                    ngrp_miles = int(ctx.get("NgrpMiles", 0) or 0)
                    pax_miles = int(pax_prices[0].get("Miles", 0) if pax_prices else 0)
                    miles = ngrp_miles or pax_miles
                    if miles == 0:
                        continue
                    ref_fare = ctx.get("ReferenceFare", {})
                    taxes = float(ref_fare.get("Amount", 0) or 0)
                    cabin_str = prod.get("CabinType", "Economy")
                    fare_class = prod.get("BookingCode", "")
                    total_dur = sum(s.duration_minutes for s in segments) if segments else 0
                    stops = len(segments) - 1 if segments else 0

                    offers.append(AwardOffer(
                        depart_date=depart_date or "",
                        miles_required=miles,
                        taxes_fees=taxes,
                        stops=stops,
                        cabin=cabin_str,
                        total_seats_available=1,
                        total_duration_minutes=total_dur,
                        segments=segments,
                        query_origin=origin.upper(),
                        query_destination=destination.upper(),
                    ))
        return offers

    @staticmethod
    def _parse_flight_segments(flight: dict[str, Any]) -> list[FlightSegment]:
        segments: list[FlightSegment] = []
        conns = flight.get("Connections", [])
        dep_dt = flight.get("DepartDateTime", "")
        arr_dt = flight.get("DestinationDateTime", "")

        if not conns:
            segments.append(FlightSegment(
                airline=flight.get("MarketingCarrier", ""),
                flight_number=str(flight.get("FlightNumber", "")),
                departure_airport=flight.get("Origin", ""),
                arrival_airport=flight.get("Destination", ""),
                departure_time=dep_dt,
                arrival_time=arr_dt,
                duration_minutes=int(flight.get("TravelMinutes", 0)),
                aircraft=flight.get("Equipment", ""),
            ))
        else:
            first_conn = conns[0]
            segments.append(FlightSegment(
                airline=flight.get("MarketingCarrier", ""),
                flight_number=str(flight.get("FlightNumber", "")),
                departure_airport=flight.get("Origin", ""),
                arrival_airport=first_conn.get("Origin", ""),
                departure_time=dep_dt,
                arrival_time=first_conn.get("DepartureTime", first_conn.get("DepartDateTime", "")),
                duration_minutes=0,
                aircraft=flight.get("Equipment", ""),
            ))
            for c in conns:
                segments.append(FlightSegment(
                    airline=c.get("Carrier", flight.get("MarketingCarrier", "")),
                    flight_number=str(c.get("FlightNumber", flight.get("FlightNumber", ""))),
                    departure_airport=c.get("Origin", ""),
                    arrival_airport=c.get("Destination", ""),
                    departure_time=c.get("DepartureTime", c.get("DepartDateTime", "")),
                    arrival_time=c.get("ArrivalTime", c.get("ArriveDateTime", "")),
                    duration_minutes=int(c.get("Duration", 0)),
                    aircraft=c.get("Equipment", ""),
                ))
        return segments


    async def _ensure_browser(self) -> BrowserContext:
        if self._context and not self._context.is_closed():
            return self._context

        self._playwright = await async_playwright().start()
        profile_dir = str(self._settings.data_path / "browser_profile")

        self._context = await self._playwright.chromium.launch_persistent_context(
            profile_dir,
            headless=self._settings.browser_headless,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-features=IsolateOrigins,site-per-process",
                "--disable-site-isolation-trials",
            ],
            executable_path=_find_chrome(),
            viewport={"width": 1280, "height": 900},
            user_agent=(
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
            ),
            locale="en-US",
            timezone_id="America/New_York",
            ignore_https_errors=True,
        )
        await self._context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => false });
            Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
            Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
            window.chrome = { runtime: {} };
            const originalQuery = window.navigator.permissions.query;
            window.navigator.permissions.query = (parameters) => (
                parameters.name === 'notifications' ?
                Promise.resolve({ state: Notification.permission }) :
                originalQuery(parameters)
            );
        """)
        return self._context

    async def close(self) -> None:
        if self._context:
            await self._context.close()
            self._context = None
        if self._playwright:
            await self._playwright.stop()
            self._playwright = None
