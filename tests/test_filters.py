"""Tests for filters module."""

from filters import filter_offers, format_offer_summary, format_offer_table_rows


class TestFilterOffers:
    def test_filter_by_miles(self, sample_offers):
        result = filter_offers(sample_offers, max_miles=110000)
        assert len(result) == 2
        assert result[0].miles_required <= result[1].miles_required

    def test_filter_by_miles_none_limit(self, sample_offers):
        result = filter_offers(sample_offers, max_miles=None)
        assert len(result) == 3

    def test_exclude_mnl(self, sample_offers):
        result = filter_offers(sample_offers, max_miles=None, exclude_airports=["MNL"])
        assert len(result) == 2
        miles_list = [o.miles_required for o in result]
        assert 80000 not in miles_list

    def test_exclude_multiple_airports(self, sample_offer, sample_offer_mnl):
        result = filter_offers(
            [sample_offer, sample_offer_mnl],
            max_miles=None,
            exclude_airports=["MNL", "NRT"],
        )
        assert len(result) == 0

    def test_empty_exclude_passes_all(self, sample_offers):
        result = filter_offers(sample_offers, max_miles=None, exclude_airports=[])
        assert len(result) == 3

    def test_sort_order(self, sample_offers):
        result = filter_offers(sample_offers, max_miles=200000)
        for i in range(len(result) - 1):
            assert result[i].miles_required <= result[i + 1].miles_required

    def test_empty_input(self):
        result = filter_offers([], max_miles=110000, exclude_airports=["MNL"])
        assert result == []

    def test_exclude_case_insensitive(self, sample_offer_mnl):
        result = filter_offers([sample_offer_mnl], max_miles=None, exclude_airports=["mnl"])
        assert len(result) == 0


class TestFormatSummary:
    def test_summary_contains_key_fields(self, sample_offer):
        summary = format_offer_summary([sample_offer])
        assert "2026-09-15" in summary
        assert "Business" in summary
        assert "UA837" in summary
        assert "SFO" in summary

    def test_summary_empty(self):
        summary = format_offer_summary([])
        assert "No matching" in summary


class TestFormatTableRows:
    def test_html_contains_tr(self, sample_offer):
        html = format_offer_table_rows([sample_offer])
        assert "<tr>" in html
        assert "UA837" in html

    def test_html_multiple_offers(self, sample_offer, sample_offer_mnl):
        html = format_offer_table_rows([sample_offer, sample_offer_mnl])
        tr_count = html.count("<tr>")
        assert tr_count == 2
