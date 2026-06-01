from kudostracker.matching import normalize_kudoer, normalize_follower


def test_normalize_kudoer_basic():
    assert normalize_kudoer("Joshua", "D.") == ("joshua", "d")


def test_normalize_kudoer_accents():
    assert normalize_kudoer("Hélène", "Č.") == ("helene", "c")


def test_normalize_kudoer_empty_lastname():
    assert normalize_kudoer("seamoon", "‎.") == ("seamoon", "")
    assert normalize_kudoer("anon", None) == ("anon", "")
    assert normalize_kudoer(None, None) == ("", "")


def test_normalize_follower_full_name():
    assert normalize_follower("Joshua Dupont") == ("joshua", "d")


def test_normalize_follower_single_name():
    assert normalize_follower("Madonna") == ("madonna", "")


def test_normalize_follower_accents():
    assert normalize_follower("François Dépardieu") == ("francois", "d")


def test_normalize_follower_multipart_last():
    # "Jean Pierre Martin" — first = Jean, last = "Pierre Martin", initial = P
    assert normalize_follower("Jean Pierre Martin") == ("jean", "p")


def test_normalize_kudoer_matches_normalize_follower():
    assert normalize_kudoer("François", "D.") == normalize_follower("François Dupont")
