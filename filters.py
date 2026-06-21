"""Result filtering for United Airlines award flight search."""

from __future__ import annotations

from scraper import AwardOffer


def filter_offers(
    offers: list[AwardOffer],
    max_miles: int | None = None,
    exclude_airports: list[str] | None = None,
) -> list[AwardOffer]:
    if exclude_airports is None:
        exclude_airports = []
    exclude_set = set(a.upper() for a in exclude_airports)

    filtered = offers

    if max_miles is not None:
        filtered = [o for o in filtered if o.miles_required <= max_miles]

    if exclude_set:
        filtered = [
            o for o in filtered
            if not any(
                seg.departure_airport.upper() in exclude_set
                or seg.arrival_airport.upper() in exclude_set
                for seg in o.segments
            )
        ]

    return sorted(filtered, key=lambda o: (o.miles_required, o.taxes_fees))


def format_offer_summary(offers: list[AwardOffer]) -> str:
    if not offers:
        return "No matching flights found."
    lines = []
    for o in offers:
        route_parts = []
        for seg in o.segments:
            route_parts.append(f"{seg.departure_airport}->{seg.arrival_airport}")
        route = " / ".join(route_parts) if route_parts else "-"
        flight_nums = " / ".join(seg.flight_number for seg in o.segments if seg.flight_number)
        lines.append(
            f"  {o.depart_date} | {o.cabin} | {o.stops} stop(s) | "
            f"{o.miles_required:,} mi + ${o.taxes_fees:.2f} | "
            f"{o.total_seats_available} seat(s) | {flight_nums} | {route}"
        )
    return "\n".join(lines)


def format_offer_table_rows(offers: list[AwardOffer]) -> str:
    rows = ""
    for o in offers:
        first_seg = o.segments[0] if o.segments else None
        last_seg = o.segments[-1] if o.segments else None
        flight = f"{first_seg.flight_number}" if first_seg else ""
        dep = _short_time(first_seg.departure_time) if first_seg else ""
        arr = _short_time(last_seg.arrival_time) if last_seg else ""
        flight_col = f"{flight} {dep}-{arr}" if flight else "-"
        duration = (
            f"{o.total_duration_minutes // 60}h{o.total_duration_minutes % 60}m"
            if o.total_duration_minutes else "-"
        )
        rows += f"""
        <tr>
            <td style="padding:8px;border-bottom:1px solid #ddd;text-align:center;">{o.depart_date}</td>
            <td style="padding:8px;border-bottom:1px solid #ddd;text-align:center;">{o.stops}</td>
            <td style="padding:8px;border-bottom:1px solid #ddd;text-align:center;">{duration}</td>
            <td style="padding:8px;border-bottom:1px solid #ddd;text-align:center;">{o.cabin.title()}</td>
            <td style="padding:8px;border-bottom:1px solid #ddd;text-align:center;font-weight:bold;color:#e53935;">{o.miles_required:,}</td>
            <td style="padding:8px;border-bottom:1px solid #ddd;text-align:center;">${o.taxes_fees:.2f}</td>
            <td style="padding:8px;border-bottom:1px solid #ddd;text-align:center;">{o.total_seats_available}</td>
            <td style="padding:8px;border-bottom:1px solid #ddd;text-align:center;">{flight_col}</td>
        </tr>"""
    return rows


def _short_time(iso_str: str) -> str:
    if not iso_str:
        return "?"
    if "T" in iso_str:
        return iso_str[11:16]
    return iso_str[:5]
