from src.rag import history


def test_history_caps_and_strips():
    history.clear("s")
    for i in range(8):
        history.add_exchange("s", f"q{i}", f"a{i} [1][2]")
    h = history.get_history("s")
    assert len(h) == 6
    assert h[0] == ("q2", "a2") and h[-1] == ("q7", "a7")


def test_history_is_per_session_and_clearable():
    history.clear("a"); history.clear("b")
    history.add_exchange("a", "q", "x")
    assert history.get_history("b") == []
    history.clear("a")
    assert history.get_history("a") == []


def test_strip_citations():
    assert history.strip_citations("Good [1]. Also [2][3] here.") == "Good. Also here."
    assert history.strip_citations("see [docs](https://x)") == "see [docs](https://x)"
    assert history.strip_citations("list [1](https://y) stays") == "list [1](https://y) stays"
