from exam_engine.ai import sanitize_text


def test_strips_markdown_headers_and_bold():
    out = sanitize_text("## 풀이\n\n**Step 1**\n내용")
    assert "#" not in out
    assert "**" not in out
    assert "풀이" in out and "Step 1" in out


def test_strips_latex_delimiters():
    out = sanitize_text("$$-2x + 3 = x - 3$$")
    assert "$" not in out
    assert "-2x + 3 = x - 3" in out


def test_frac_to_plain():
    assert sanitize_text(r"\frac{1}{2}") == "(1)/(2)"


def test_latex_commands_to_unicode():
    out = sanitize_text(r"x \leq 3 \times 2 \geq 1")
    assert "≤" in out and "×" in out and "≥" in out
    assert "\\" not in out


def test_empty_and_plain_unchanged():
    assert sanitize_text("") == ""
    assert sanitize_text("정답: 14") == "정답: 14"


def test_collapses_blank_lines():
    assert "\n\n\n" not in sanitize_text("a\n\n\n\n\nb")
