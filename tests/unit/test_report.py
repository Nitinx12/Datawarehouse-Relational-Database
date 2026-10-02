from src.jobs._report import short_error


def test_short_error_collapses_stack_frames():
    exc = ValueError(
        "bad thing happened\n  at foo.Bar(Baz.java:1)\n  at foo.Qux(Qux.java:2)"
    )
    assert short_error(exc) == "ValueError: bad thing happened"


def test_short_error_truncates_long_messages():
    exc = RuntimeError("x" * 500)
    result = short_error(exc, max_len=50)
    assert len(result) <= len("RuntimeError: ") + 50
    assert result.endswith("...")


def test_short_error_empty_message_falls_back_to_class():
    assert short_error(ValueError("")) == "ValueError: ValueError"
