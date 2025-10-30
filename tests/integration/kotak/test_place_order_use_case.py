from modules.kotak_neo_auto_trader.application.use_cases.place_order import PlaceOrderUseCase
from modules.kotak_neo_auto_trader.application.dto.order_request import OrderRequest
from modules.kotak_neo_auto_trader.domain.value_objects.order_enums import OrderVariety, ProductType
from modules.kotak_neo_auto_trader.infrastructure.broker_adapters.mock_broker_adapter import MockBrokerAdapter


def test_place_market_buy_order_success():
    broker = MockBrokerAdapter()
    use_case = PlaceOrderUseCase(broker_gateway=broker)

    req = OrderRequest.market_buy(symbol='RELIANCE.NS', quantity=5, variety=OrderVariety.REGULAR, product_type=ProductType.CNC)
    resp = use_case.execute(req)

    assert resp.success
    assert resp.order_id is not None
    assert broker.get_order(resp.order_id) is not None


def test_place_order_validation_failure():
    broker = MockBrokerAdapter()
    use_case = PlaceOrderUseCase(broker_gateway=broker)

    # Invalid quantity
    bad_req = OrderRequest.market_buy(symbol='INFY.NS', quantity=0)
    resp = use_case.execute(bad_req)
    assert not resp.success
    assert any('Quantity' in e or 'Quantity must be positive' in e for e in resp.errors)
