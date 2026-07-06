"""Unit tests for fact anchor extraction and diff."""

from humanhand.domain.facts import diff_facts, extract_fact_anchors


class TestExtractFactAnchors:
    def test_empty_text(self) -> None:
        anchors = extract_fact_anchors("")
        assert anchors == []

    def test_numbers(self) -> None:
        text = "The price is $50.00 and there are 123 items at 3.5% interest."
        anchors = extract_fact_anchors(text)
        numbers = [a for a in anchors if a.category == "number"]
        assert len(numbers) >= 2

    def test_dates_iso(self) -> None:
        text = "The event was on 2024-01-15."
        anchors = extract_fact_anchors(text)
        dates = [a for a in anchors if a.category == "date"]
        assert len(dates) >= 1
        assert any("2024-01-15" in a.text for a in dates)

    def test_dates_written(self) -> None:
        text = "On January 15, 2024 the meeting occurred."
        anchors = extract_fact_anchors(text)
        dates = [a for a in anchors if a.category == "date"]
        assert len(dates) >= 1

    def test_entities(self) -> None:
        text = "John Smith visited New York City last week."
        anchors = extract_fact_anchors(text)
        entities = [a for a in anchors if a.category == "entity"]
        assert len(entities) >= 1
        assert any("John Smith" in a.text for a in entities)

    def test_quotes(self) -> None:
        text = 'She said "this is important" during the talk.'
        anchors = extract_fact_anchors(text)
        quotes = [a for a in anchors if a.category == "quote"]
        assert len(quotes) >= 1
        assert any("this is important" in a.text for a in quotes)

    def test_citations(self) -> None:
        text = "See the study (Smith, 2020) for details [1, 2]."
        anchors = extract_fact_anchors(text)
        citations = [a for a in anchors if a.category == "citation"]
        assert len(citations) >= 1

    def test_anchors_sorted_by_position(self) -> None:
        text = "The value 42. The date 2024-01-01."
        anchors = extract_fact_anchors(text)
        positions = [a.position for a in anchors]
        assert positions == sorted(positions)

    def test_no_duplicate_positions_for_same_type(self) -> None:
        text = "Numbers: 1, 2, and 3."
        anchors = extract_fact_anchors(text)
        num_positions = [a.position for a in anchors if a.category == "number"]
        assert len(num_positions) == len(set(num_positions))


class TestDiffFacts:
    def test_identical_text(self) -> None:
        text = "The price is $50. John Smith visited on 2024-01-15."
        report = diff_facts(text, text)
        assert report.preservation_score == 1.0
        assert len(report.omissions) == 0
        assert len(report.contradictions) == 0

    def test_omission_detected(self) -> None:
        source = "The price is $50. John Smith visited New York on 2024-01-15."
        candidate = "The price is $50. Someone visited somewhere sometime."
        report = diff_facts(source, candidate)
        assert report.preservation_score < 1.0
        assert len(report.omissions) > 0

    def test_addition_detected(self) -> None:
        source = "The price is $50."
        candidate = "The price is $50 and $100."
        report = diff_facts(source, candidate)
        assert len(report.additions) > 0

    def test_empty_source(self) -> None:
        report = diff_facts("", "some text")
        assert report.total_source_anchors == 0
        assert report.preservation_score == 1.0

    def test_empty_candidate(self) -> None:
        source = "The price is $50."
        report = diff_facts(source, "")
        assert report.preservation_score == 0.0
        assert len(report.omissions) > 0

    def test_contradiction_numeric(self) -> None:
        source = "The price is $50."
        candidate = "The price is $60."  # Same structure, different number
        report = diff_facts(source, candidate)
        # Numbers should be caught as omissions (old number gone) or contradictions
        assert report.preservation_score < 1.0 or report.has_drift

    def test_preservation_score_range(self) -> None:
        source = "A B C D E F G H I J"
        candidate = "A B C X Y Z"
        report = diff_facts(source, candidate)
        assert 0.0 <= report.preservation_score <= 1.0

    def test_report_has_drift(self) -> None:
        source = "The test involved 42 participants at Harvard University."
        candidate = "The test involved 50 participants."
        report = diff_facts(source, candidate)
        assert report.has_drift

    def test_report_has_drift_for_unsupported_addition(self) -> None:
        report = diff_facts("", 'A new claim cites "42% growth".')
        assert len(report.additions) > 0
        assert report.has_drift
