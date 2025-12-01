from modules.kotak_neo_auto_trader.orders import KotakNeoOrders


class _FakeAuth:
    def __init__(self, client):
        self._client = client

    def get_client(self):
        return self._client


class _CapturingClient:
    def __init__(self):
        self.payloads = []

    def place_order(
        self,
        *,
        exchange_segment=None,
        product=None,
        price=None,
        order_type=None,
        quantity=None,
        validity=None,
        trading_symbol=None,
        transaction_type=None,
        amo=None,
        disclosed_quantity=None,
        **extra,
    ):
        payload = {
            "exchange_segment": exchange_segment,
            "product": product,
            "price": price,
            "order_type": order_type,
            "quantity": quantity,
            "validity": validity,
            "trading_symbol": trading_symbol,
            "transaction_type": transaction_type,
            "amo": amo,
            "disclosed_quantity": disclosed_quantity,
        }
        payload.update(extra)
        self.payloads.append(payload)
        return {"stat": "Ok", "nOrdNo": "12345"}


def _build_orders_api():
    client = _CapturingClient()
    auth = _FakeAuth(client)
    orders_api = KotakNeoOrders(auth)
    return orders_api, client


def test_market_buy_payload_uses_required_schema():
    orders_api, client = _build_orders_api()

    orders_api.place_market_buy(
        symbol="YESBANK-EQ",
        quantity=1,
        variety="AMO",
        exchange="NSE",
        product="CNC",
    )

    assert client.payloads, "Expected client.place_order to be invoked"
    payload = client.payloads[-1]

    assert payload["exchange_segment"] == "nse_cm"
    assert payload["product"] == "CNC"
    assert payload["price"] == "0"
    assert payload["order_type"] == "MKT"
    assert payload["quantity"] == "1"
    assert payload["validity"] == "DAY"
    assert payload["trading_symbol"] == "YESBANK-EQ"
    assert payload["transaction_type"] == "B"
    assert payload["amo"] == "YES"
    assert payload["disclosed_quantity"] == "0"


def test_limit_sell_payload_sets_price_string_and_regular_amo():
    orders_api, client = _build_orders_api()

    orders_api.place_limit_sell(
        symbol="RELIANCE-EQ",
        quantity=5,
        price=2450.55,
        variety="REGULAR",
        exchange="NSE",
        product="CNC",
    )

    payload = client.payloads[-1]

    assert payload["price"] == "2450.55"
    assert payload["order_type"] == "L"
    assert payload["transaction_type"] == "S"
    assert payload["amo"] == "NO"
    assert payload["quantity"] == "5"
