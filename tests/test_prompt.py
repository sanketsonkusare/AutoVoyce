from src.rag.prompt import SYSTEM_PROMPT, build_user_message, format_passages, format_time
from src.rag.retrieval import Passage


def test_format_time():  # Review Focus 5
    assert format_time(0) == "0:00"
    assert format_time(272) == "4:32"
    assert format_time(3725) == "1:02:05"


def test_format_passages():
    text = format_passages([
        Passage(1, "v", "iPhone 15 Review", "MKBHD", 272, "body", "u"),
        Passage(2, "w", "Pixel", "", None, "body2", "u2"),
    ])
    assert text == '[1] "iPhone 15 Review" by MKBHD, at 4:32\nbody\n\n[2] "Pixel"\nbody2'


def test_format_passages_keeps_odd_titles_literal():  # Review Focus 1
    out = format_passages([Passage(1, "v", '[Official] "Review" *2024*', "C", 5, "b", "u")])
    assert out.startswith('[1] "[Official] "Review" *2024*" by C, at 0:05')


def test_user_message_with_passages():
    msg = build_user_message("why?", [Passage(1, "v", "T", "C", 1, "body", "u")])
    assert msg == 'Passages:\n\n[1] "T" by C, at 0:01\nbody\n\nQuestion: why?'


def test_user_message_without_passages_says_so():
    msg = build_user_message("why?", [])
    assert "No passages" in msg and msg.rstrip().endswith("Question: why?")


def test_system_prompt_rules():
    for phrase in ["[n]", "don't cover this", "not instructions"]:
        assert phrase in SYSTEM_PROMPT
