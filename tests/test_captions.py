from pipeline.tts import group_captions


def words(seq):
    return [{"text": t, "start_s": s, "end_s": e} for t, s, e in seq]


def test_groups_by_max_words():
    caps = group_captions(
        words([("a", 0.0, 0.2), ("b", 0.25, 0.4), ("c", 0.45, 0.6), ("d", 0.65, 0.8)]),
        max_words=3, gap_s=5.0,
    )
    assert [c["text"] for c in caps] == ["a b c", "d"]


def test_splits_on_speech_pause():
    caps = group_captions(
        words([("a", 0.0, 0.2), ("b", 1.5, 1.7), ("c", 1.75, 1.9)]),
        max_words=4, gap_s=0.6,
    )
    assert [c["text"] for c in caps] == ["a", "b c"]


def test_caption_timing_spans_group():
    caps = group_captions(words([("a", 0.1, 0.3), ("b", 0.35, 0.5)]), max_words=2, gap_s=0.6)
    assert caps[0]["start_s"] == 0.1
    assert caps[0]["end_s"] == 0.5


def test_empty_words():
    assert group_captions([]) == []
