from src.services.tiktok_caption import normalize_hashtags, strip_trailing_hashtags


def test_normalize_hashtags_dedupes_and_caps_repeated_blocks():
    tags = normalize_hashtags(
        [
            "#storytime",
            "reddit",
            "#chefeToxico #obedienciaCega #chefeToxico",
            "prazosPerdidos#fyp",
            "mãeTóxica",
            "extra",
        ]
    )

    assert tags == [
        "fyp",
        "storytime",
        "reddit",
        "chefeToxico",
        "obedienciaCega",
        "prazosPerdidos",
    ]


def test_strip_trailing_hashtags_keeps_title_and_removes_existing_block():
    assert (
        strip_trailing_hashtags(
            "Meu chefe me proibiu de decidir sozinho  #fyp #storytime #reddit"
        )
        == "Meu chefe me proibiu de decidir sozinho"
    )
