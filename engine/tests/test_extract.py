from exam_engine.extract import split_problems, _split_choices


def test_split_problems_basic():
    pages = [
        "1. 첫 번째 문제입니다.\n계속되는 내용\n2. 두 번째 문제\n3) 세 번째 문제",
    ]
    problems = split_problems(pages)
    assert [p.number for p in problems] == [1, 2, 3]
    assert "첫 번째 문제" in problems[0].text
    assert "계속되는 내용" in problems[0].text


def test_split_problems_tracks_pages():
    pages = ["1. 문제 하나", "2. 문제 둘"]
    problems = split_problems(pages)
    assert problems[0].page == 1
    assert problems[1].page == 2


def test_split_choices_circled():
    body = "다음 중 옳은 것은? ① 가 ② 나 ③ 다 ④ 라 ⑤ 마"
    stem, choices = _split_choices(body)
    assert stem == "다음 중 옳은 것은?"
    assert choices == ["가", "나", "다", "라", "마"]


def test_split_choices_none():
    stem, choices = _split_choices("그냥 서술형 문제")
    assert stem == "그냥 서술형 문제"
    assert choices == []


def test_ignores_text_before_first_problem():
    pages = ["머리말 텍스트\n수학 영역\n1. 진짜 첫 문제"]
    problems = split_problems(pages)
    assert len(problems) == 1
    assert problems[0].number == 1
