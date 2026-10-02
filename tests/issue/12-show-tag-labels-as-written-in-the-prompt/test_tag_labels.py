import types

START, END, COMMA = 1, 2, 3


class FakeClip:
    """Hands split_tags() token pieces as the CLIP BPE produced them.

    The pieces in the tests are the real tokenizer's output for the prompt
    next to them.
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


def labels(daam, clip, text, *chunks):
    tokens = {"l": list(chunks), daam.PROMPT_TEXT_KEY: text}
    return [tag for tag, _ in daam.split_tags(clip, tokens)]


def test_labels_keep_the_prompt_text(daam):
    text = (
        r"astesia \(arknights\), torn see-through kneehighs, "
        "(light particles,:-1.2) posing, Gray loose-fit swim shirt"
    )
    clip = FakeClip()
    chunk = clip.chunk(
        "aste", "sia</w>", "(</w>", "ar", "knights</w>", "),</w>",
        "torn</w>", "see</w>", "-</w>", "through</w>", "kne", "e", "highs</w>", ",</w>",
        "light</w>", "particles</w>", ",</w>", "posing</w>", ",</w>",
        "gray</w>", "loose</w>", "-</w>", "fit</w>", "swim</w>", "shirt</w>",
    )  # fmt: skip

    assert labels(daam, clip, text, chunk) == [
        r"astesia \(arknights\)",
        "torn see-through kneehighs",
        "light particles",
        "posing",
        "Gray loose-fit swim shirt",
    ]


def test_a_leading_escape_stays_on_the_label(daam):
    clip = FakeClip()
    chunk = clip.chunk("(</w>", "ar", "knights</w>", "),</w>", "red</w>")

    assert labels(daam, clip, r"\(arknights\), red", chunk) == [
        r"\(arknights\)",
        "red",
    ]


def test_labels_follow_the_prompt_across_break(daam):
    clip = FakeClip()
    first = clip.chunk("see</w>", "-</w>", "through</w>")
    second = clip.chunk("see</w>", "-</w>", "through</w>", ",</w>", "red</w>")

    assert labels(daam, clip, "see-through BREAK see-through, red", first, second) == [
        "see-through",
        "see-through",
        "red",
    ]


def test_a_label_missing_from_the_prompt_stays_decoded(daam):
    clip = FakeClip()
    chunk = clip.chunk("see</w>", "-</w>", "through</w>")

    assert labels(daam, clip, "something else", chunk) == ["see - through"]
