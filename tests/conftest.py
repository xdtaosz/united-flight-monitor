"""pytest fixtures for united-flight-monitor."""

from __future__ import annotations

import pytest
from datetime import date

from scraper import AwardOffer, FlightSegment


@pytest.fixture
def sample_segment():
    return FlightSegment(
        airline="UA",
        flight_number="UA837",
        departure_airport="SFO",
        arrival_airport="NRT",
        departure_time="2026-09-15T10:30:00",
        arrival_time="2026-09-15T14:00:00",
        duration_minutes=630,
        aircraft="B789",
        fare_class="I",
    )


@pytest.fixture
def sample_segment_mnl():
    return FlightSegment(
        airline="UA",
        flight_number="UA189",
        departure_airport="SFO",
        arrival_airport="MNL",
        departure_time="2026-09-15T01:00:00",
        arrival_time="2026-09-16T05:00:00",
        duration_minutes=840,
    )


@pytest.fixture
def sample_offer(sample_segment):
    return AwardOffer(
        depart_date="2026-09-15",
        miles_required=99000,
        taxes_fees=45.60,
        stops=0,
        cabin="Business",
        total_seats_available=2,
        total_duration_minutes=630,
        segments=[sample_segment],
        query_origin="SFO",
        query_destination="BJS",
    )


@pytest.fixture
def sample_offer_mnl(sample_segment_mnl):
    seg2 = FlightSegment(
        departure_airport="MNL",
        arrival_airport="BJS",
        flight_number="UA190",
        departure_time="2026-09-16T07:00:00",
        arrival_time="2026-09-16T13:00:00",
        duration_minutes=360,
    )
    return AwardOffer(
        depart_date="2026-09-15",
        miles_required=80000,
        taxes_fees=35.00,
        stops=1,
        cabin="Business",
        segments=[sample_segment_mnl, seg2],
        query_origin="SFO",
        query_destination="BJS",
    )


@pytest.fixture
def sample_offers(sample_offer, sample_offer_mnl):
    offer_high = AwardOffer(
        depart_date="2026-09-20",
        miles_required=125000,
        taxes_fees=50.00,
        stops=1,
        cabin="Business",
        segments=[],
    )
    return [sample_offer, sample_offer_mnl, offer_high]
