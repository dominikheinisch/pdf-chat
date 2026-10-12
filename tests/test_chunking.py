import re
from itertools import pairwise

from chunking import Chunk, chunk


def test_short_pages_share_one_chunk_that_spans_them():
    pages = ["Invoice 2024-17\n\nTotal due: 1,250 EUR.", "Late fees apply."]

    assert chunk(pages) == [
        Chunk("Invoice 2024-17\n\nTotal due: 1,250 EUR.\n\nLate fees apply.", 1, 2)
    ]


def sentence(n):
    # About 15 tokens each.
    return f"Sentence {n:03d} adds one more fact to this long running report."


def page_of(first, count):
    return " ".join(sentence(n) for n in range(first, first + count))


def numbers(c):
    return [int(n) for n in re.findall(r"Sentence (\d+)", c.text)]


def tokens(text):
    return len(text) // 4


def test_long_text_is_split_into_chunks_of_about_800_tokens():
    pages = [page_of(page * 40, 40) for page in range(10)]

    chunks = chunk(pages)

    assert len(chunks) > 5
    assert all(tokens(c.text) <= 800 for c in chunks)
    assert all(tokens(c.text) >= 400 for c in chunks[:-1])


def test_consecutive_chunks_overlap_by_about_100_tokens():
    chunks = chunk([page_of(0, 200)])

    assert len(chunks) > 1
    for previous, following in pairwise(chunks):
        repeated = [n for n in numbers(following) if n in numbers(previous)]
        assert repeated == numbers(previous)[-len(repeated) :]
        assert 50 <= tokens(" ".join(sentence(n) for n in repeated)) <= 100


def test_each_chunk_records_the_pages_it_spans():
    pages = [page_of(page * 40, 40) for page in range(5)]

    chunks = chunk(pages)

    for c in chunks:
        first = int(c.text.split()[1])
        last = int(c.text.split()[-10])
        assert (c.page_start, c.page_end) == (first // 40 + 1, last // 40 + 1)
    assert any(c.page_start != c.page_end for c in chunks)


def test_pages_without_text_add_nothing():
    assert chunk(["", "Only page two has text.", ""]) == [
        Chunk("Only page two has text.", 2, 2)
    ]


def test_a_heading_starts_a_new_chunk_once_the_current_one_is_half_full():
    body = page_of(0, 35)
    pages = [f"{body}\n\nPayment terms\n\nLate payments add interest."]

    chunks = chunk(pages)

    assert chunks[-1].text.startswith("Payment terms")
    assert chunks[0].text.endswith(sentence(34))


def test_a_heading_stays_with_its_text_when_the_chunk_has_room():
    pages = ["Short intro.\n\nPayment terms\n\nLate payments add interest."]

    assert len(chunk(pages)) == 1
