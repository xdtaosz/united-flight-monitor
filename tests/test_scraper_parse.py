"""Offline parse tests for UnitedScraper response parsing (no browser needed)."""

import pytest
from datetime import date

from scraper import UnitedScraper


class TestCalendarResponseParsing:
    def test_parse_business_calendar(self):
        scraper = UnitedScraper()
        sample = {
            "data": {
                "Trips": [{
                    "Flights": [{
                        "DepartDateTime": "2026-09-15T08:00:00",
                        "Products": [{
                            "CabinType": "Business",
                            "Context": {
                                "NgrpMiles": 99000,
                                "ReferenceFare": {"Amount": 5.60},
                            },
                        }],
                    }],
                }],
            }
        }

    def test_over_threshold_excluded(self):
        scraper = UnitedScraper()
        sample = {
            "data": {
                "Trips": [{
                    "Flights": [{
                        "DepartDateTime": "2026-09-15T08:00:00",
                        "Products": [{
                            "CabinType": "Business",
                            "Context": {
                                "NgrpMiles": 125000,
                                "ReferenceFare": {"Amount": 5.60},
                            },
                        }],
                    }],
                }],
            }
        }

    def test_economy_ignored(self):
        scraper = UnitedScraper()
        sample = {
            "data": {
                "Trips": [{
                    "Flights": [{
                        "DepartDateTime": "2026-09-15T08:00:00",
                        "Products": [{
                            "CabinType": "Economy",
                            "Context": {
                                "NgrpMiles": 30000,
                                "ReferenceFare": {"Amount": 5.60},
                            },
                        }],
                    }],
                }],
            }
        }


class TestFlightsResponseParsing:
    def test_parse_single_flight(self):
        scraper = UnitedScraper()
        data = {
            "data": {
                "Trips": [{
                    "DepartDate": "2026-09-15",
                    "Flights": [{
                        "FlightNumber": "837",
                        "MarketingCarrier": "UA",
                        "Origin": "SFO",
                        "Destination": "NRT",
                        "DepartDateTime": "2026-09-15T10:30:00",
                        "DestinationDateTime": "2026-09-15T14:00:00",
                        "TravelMinutes": 630,
                        "Equipment": "B789",
                        "Connections": [],
                        "Products": [{
                            "CabinType": "Business",
                            "BookingCode": "I",
                            "Context": {
                                "NgrpMiles": 99000,
                                "ReferenceFare": {"Amount": 5.60},
                            },
                        }],
                    }],
                }],
            }
        }
        offers = scraper._parse_flights_response(data, "SFO", "BJS")
        assert len(offers) == 1
        offer = offers[0]
        assert offer.miles_required == 99000
        assert offer.taxes_fees == 5.60
        assert offer.cabin == "Business"
        assert offer.stops == 0
        assert len(offer.segments) == 1
        seg = offer.segments[0]
        assert seg.flight_number == "837"
        assert seg.departure_airport == "SFO"
        assert seg.arrival_airport == "NRT"

    def test_parse_with_connections(self):
        scraper = UnitedScraper()
        data = {
            "data": {
                "Trips": [{
                    "DepartDate": "2026-09-15",
                    "Flights": [{
                        "FlightNumber": "189",
                        "MarketingCarrier": "UA",
                        "Origin": "SFO",
                        "Destination": "BJS",
                        "DepartDateTime": "2026-09-15T01:00:00",
                        "DestinationDateTime": "2026-09-16T13:00:00",
                        "TravelMinutes": 2160,
                        "Equipment": "B77W",
                        "Connections": [{
                            "Carrier": "UA",
                            "FlightNumber": "190",
                            "Origin": "MNL",
                            "Destination": "BJS",
                            "DepartureTime": "2026-09-16T07:00:00",
                            "ArrivalTime": "2026-09-16T13:00:00",
                            "Duration": 360,
                            "Equipment": "B789",
                        }],
                        "Products": [{
                            "CabinType": "Business",
                            "BookingCode": "I",
                            "Context": {
                                "NgrpMiles": 88000,
                                "ReferenceFare": {"Amount": 35.00},
                            },
                        }],
                    }],
                }],
            }
        }
        offers = scraper._parse_flights_response(data, "SFO", "BJS")
        assert len(offers) == 1
        offer = offers[0]
        assert offer.stops == 1
        assert len(offer.segments) == 2
        assert offer.segments[0].departure_airport == "SFO"
        assert offer.segments[0].arrival_airport == "MNL"
        assert offer.segments[1].departure_airport == "MNL"
        assert offer.segments[1].arrival_airport == "BJS"

    def test_zero_miles_skipped(self):
        scraper = UnitedScraper()
        data = {
            "data": {
                "Trips": [{
                    "DepartDate": "2026-09-15",
                    "Flights": [{
                        "FlightNumber": "837",
                        "Origin": "SFO",
                        "Destination": "NRT",
                        "DepartDateTime": "2026-09-15T10:30:00",
                        "DestinationDateTime": "2026-09-15T14:00:00",
                        "TravelMinutes": 630,
                        "Connections": [],
                        "Products": [{
                            "CabinType": "Business",
                            "BookingCode": "I",
                            "Context": {
                                "NgrpMiles": 0,
                                "ReferenceFare": {"Amount": 5.60},
                            },
                        }],
                    }],
                }],
            }
        }
        offers = scraper._parse_flights_response(data, "SFO", "BJS")
        assert len(offers) == 0


class TestPayloadBuilding:
    def test_business_payload(self):
        scraper = UnitedScraper()
        payload = scraper._build_api_payload("SFO", "BJS", date(2026, 9, 15), "business")
        assert payload["AwardTravel"] is True
        assert payload["CabinPreferenceMain"] == "premium"
        tripreq = payload["Trips"][0]
        assert tripreq["Origin"] == "SFO"
        assert tripreq["Destination"] == "BJS"
        assert tripreq["SearchFiltersIn"]["FareFamily"] == "BUSINESS"

    def test_economy_payload(self):
        scraper = UnitedScraper()
        payload = scraper._build_api_payload("LAX", "NRT", date(2026, 10, 1), "economy")
        assert payload["CabinPreferenceMain"] == "eco"
        tripreq = payload["Trips"][0]
        assert tripreq["SearchFiltersIn"]["FareFamily"] == "ECO"
