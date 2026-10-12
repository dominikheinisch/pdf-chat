from answers import Source
from citations import CitationNumbering


def render(*parts):
    numbering = CitationNumbering()
    text = "".join(numbering.feed(part) for part in parts) + numbering.flush()
    return text, numbering.sources


def test_numbers_citations_in_order_of_first_appearance():
    text, sources = render(
        "Due 30 June [invoice.pdf, p. 1], with interest [contract.pdf, pp. 4–5]. "
        "Again [invoice.pdf, p. 1]."
    )

    assert text == "Due 30 June [1], with interest [2]. Again [1]."
    assert sources == [
        Source(1, "invoice.pdf", 1, 1, ""),
        Source(2, "contract.pdf", 4, 5, ""),
    ]


def test_handles_citations_split_across_streamed_chunks():
    text, sources = render("Due [inv", "oice.pdf, p", ". 2", "] soon.")

    assert text == "Due [1] soon."
    assert sources == [Source(1, "invoice.pdf", 2, 2, "")]


def test_leaves_other_brackets_alone():
    text, sources = render("See [note] and [1] and [", "unfinished")

    assert text == "See [note] and [1] and [unfinished"
    assert sources == []


def test_accepts_a_hyphen_in_page_ranges():
    _, sources = render("[a.pdf, pp. 3-4]")

    assert sources == [Source(1, "a.pdf", 3, 4, "")]
