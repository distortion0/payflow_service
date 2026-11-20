from app.signature import verify_signature

SECRET = "whsec_test_123"
BODY = b'{"id":"evt_1","type":"account.funded"}'
SIGNATURE = "ef52fc75bf179b9e591a3415721fb28b525dcde4a89cf478d965c4ae1e092af9"


def test_accepts_matching_signature() -> None:
    assert verify_signature(BODY, SIGNATURE, SECRET)


def test_rejects_missing_header() -> None:
    assert not verify_signature(BODY, None, SECRET)


def test_rejects_wrong_signature() -> None:
    assert not verify_signature(BODY, "00" * 32, SECRET)
    assert not verify_signature(BODY, "not even hex", SECRET)
    assert not verify_signature(BODY, "підпис", SECRET)


def test_rejects_other_secret() -> None:
    assert not verify_signature(BODY, SIGNATURE, "whsec_live_456")


def test_rejects_modified_body() -> None:
    assert not verify_signature(BODY + b" ", SIGNATURE, SECRET)
    assert not verify_signature(BODY.replace(b"evt_1", b"evt_2"), SIGNATURE, SECRET)
