import types

START, END, COMMA = 1, 2, 3


class FakeClip:
    """Hands split_tags() token pieces as the CLIP BPE produced them.

    The pieces in the tests are the real tokenizer's output: weight parens
    never reach it, escaped ones arrive as literal pieces, and "\\)," comes out
    as the single piece "),</w>".
    """

    def __init__(self):
        self.vocab = {",</w>": COMMA}
        self.tokenizer = types.SimpleNamespace(inv_vocab={COMMA: ",</w>"})

    def tokenize(self, text):
        ids = [COMMA] if text == "," else []
        return {"l": [[(i, 1.0) for i in (START, *ids, END)]]}

    def chunk(self, *pieces):
        for piece in pieces:
            if piece not in self.vocab:
                self.vocab[piece] = len(self.vocab) + COMMA
                self.tokenizer.inv_vocab[self.vocab[piece]] = piece
        ids = [self.vocab[piece] for piece in pieces]
        return [(i, 1.0) for i in (START, *ids, END)]


def test_open_paren_does_not_swallow_later_tags(daam):
    # annoyed, >:\(, ciloranko, mikozin
    clip = FakeClip()
    chunk = clip.chunk(
        "annoyed</w>", ",</w>", ">", ":", "(", ",</w>",
        "cil", "oran", "ko</w>", ",</w>", "mikozin</w>",
    )  # fmt: skip

    assert daam.split_tags(clip, {"l": [chunk]}) == [
        ("annoyed", [1]),
        (">:(", [3, 4, 5]),
        ("ciloranko", [7, 8, 9]),
        ("mikozin", [11]),
    ]


def test_open_paren_does_not_reach_the_next_chunk(daam):
    # >:\( BREAK smell, shade
    clip = FakeClip()
    first = clip.chunk(">", ":", "(")
    second = clip.chunk("smell</w>", ",</w>", "shade</w>")

    assert daam.split_tags(clip, {"l": [first, second]}) == [
        (">:(", [1, 2, 3]),
        ("smell", [6]),
        ("shade", [8]),
    ]


def test_emoticons_with_parens_split_like_any_tag(daam):
    # >:\(, smile, ;\), shade
    clip = FakeClip()
    chunk = clip.chunk(
        ">", ":", "(", ",</w>", "smile</w>", ",</w>", ";", "),</w>", "shade</w>"
    )

    assert [tag for tag, _ in daam.split_tags(clip, {"l": [chunk]})] == [
        ">:(",
        "smile",
        ";)",
        "shade",
    ]


def test_comma_glued_to_a_close_paren_separates(daam):
    # pozyomka \(arknights\), annoyed
    clip = FakeClip()
    chunk = clip.chunk(
        "pozyomka</w>", "(</w>", "arknights</w>", "),</w>", "annoyed</w>"
    )

    assert daam.split_tags(clip, {"l": [chunk]}) == [
        ("pozyomka ( arknights )", [1, 2, 3, 4]),
        ("annoyed", [5]),
    ]
