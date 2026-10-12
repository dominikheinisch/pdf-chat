from answers import Source
from quotes import check_quotes

PAGES = {
    "invoice.pdf": [
        "Invoice 2024-17\n\nTotal due: 1,250 EUR by 30 June.",
        "Late payments add 2% inter-\nest per month after the ﬁrst reminder.",
        "Disputes go to the courts of Berlin under German law.",
    ]
}


def source(page, quote=""):
    return Source(1, "invoice.pdf", page, page, quote)


def test_attaches_a_quote_found_on_the_cited_page():
    answer = 'It says "Total due: 1,250 EUR by 30 June" [1].'

    [checked] = check_quotes(answer, [source(1)], PAGES)

    assert checked == source(1, "Total due: 1,250 EUR by 30 June")


def test_matches_after_normalising_case_spacing_hyphens_and_ligatures():
    answer = (
        'Fees: "late payments add 2%  interest per month after the first reminder" [1]'
    )

    [checked] = check_quotes(answer, [source(2)], PAGES)

    assert checked.warning is None
    assert checked.page_start == 2


def test_corrects_the_page_when_the_quote_is_on_another_page():
    answer = 'Venue: "Disputes go to the courts of Berlin" [1].'

    [checked] = check_quotes(answer, [source(1)], PAGES)

    assert (checked.page_start, checked.page_end) == (3, 3)
    assert checked.warning is None


def test_flags_a_quote_that_is_not_in_the_document():
    answer = 'It says "payment is due within fourteen days" [1].'

    [checked] = check_quotes(answer, [source(1)], PAGES)

    assert checked.warning == "⚠️ quote not found in invoice.pdf"
    assert checked.page_start == 1


def test_ignores_quotes_shorter_than_five_words():
    answer = 'Marked "net 30 days" [1] in "Total due" terms [1].'

    [checked] = check_quotes(answer, [source(1)], PAGES)

    assert checked == source(1)


def test_accepts_curly_quotes():
    answer = "It says “Total due: 1,250 EUR by 30 June” [1]."

    [checked] = check_quotes(answer, [source(1)], PAGES)

    assert checked.quote == "Total due: 1,250 EUR by 30 June"
