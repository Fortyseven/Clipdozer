from app.utils.timefmt import format_time


def test_format_time_edge_cases():
    assert format_time(-1.0) == "00:00.000"  # negative clamps
    assert format_time(0.0) == "00:00.000"
    assert format_time(0.9996) == "00:01.000"
    assert format_time(61.0) == "01:01.000"
    assert format_time(3600 + 62.5).startswith("61:02")


def test_format_time_precision():
    assert format_time(1.2344) == "00:01.234"
    assert format_time(1.2345) == "00:01.235"  # rounds up (half-up)
