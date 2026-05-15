# ruff: noqa: E501
"""Branch coverage for broker._test_kotak_neo_login and _test_kotak_neo_2fa."""

from server.app.routers import broker as br


class _ClientLoginErr:
    def login(self, **_kwargs):
        raise TypeError("NoneType can only concatenate str")


class _ClientLoginDictErr:
    def login(self, **_kwargs):
        return {"error": [{"message": "bad creds"}]}


class _ClientLoginNone:
    def login(self, **_kwargs):
        return None


class _Client2faNone:
    def session_2fa(self, **_kwargs):
        return None


class _Client2faDict:
    def session_2fa(self, **_kwargs):
        return {"error": [{"message": "2fa bad"}]}


class _Client2faExc:
    def session_2fa(self, **_kwargs):
        raise RuntimeError("NoneType.get is broken")


def _creds(**kwargs):
    base = dict(
        consumer_key="k",
        consumer_secret="s",
        mobile_number="999",
        password="p",
        mpin=None,
        totp_secret=None,
        environment="prod",
    )
    base.update(kwargs)
    return br.KotakNeoCreds(**base)


def test_kotak_neo_login_typeerror_nonetype_concat():
    ok, msg = br._test_kotak_neo_login(_ClientLoginErr(), _creds())
    assert ok is False
    assert "SDK" in msg or "NoneType" in msg


def test_kotak_neo_login_dict_error():
    ok, msg = br._test_kotak_neo_login(_ClientLoginDictErr(), _creds())
    assert ok is False
    assert "bad creds" in msg


def test_kotak_neo_login_none_response():
    ok, msg = br._test_kotak_neo_login(_ClientLoginNone(), _creds())
    assert ok is False


def test_kotak_neo_login_missing_mobile():
    ok, msg = br._test_kotak_neo_login(_ClientLoginNone(), _creds(mobile_number=None, password="p"))
    assert ok is False


def test_kotak_neo_login_totp_branch():
    class _C:
        def login(self, **_kwargs):
            return {"ok": True}

    ok, msg = br._test_kotak_neo_login(_C(), _creds(mpin=None, totp_secret="sec"))
    assert ok is True


def test_kotak_neo_2fa_empty_mpin():
    ok, msg = br._test_kotak_neo_2fa(object(), "")
    assert ok is False


def test_kotak_neo_2fa_none_response():
    ok, msg = br._test_kotak_neo_2fa(_Client2faNone(), "1234")
    assert ok is True


def test_kotak_neo_2fa_error_list():
    ok, msg = br._test_kotak_neo_2fa(_Client2faDict(), "1234")
    assert ok is False
    assert "2fa bad" in msg


def test_kotak_neo_2fa_nonetype_get_success():
    ok, msg = br._test_kotak_neo_2fa(_Client2faExc(), "1234")
    assert ok is True
