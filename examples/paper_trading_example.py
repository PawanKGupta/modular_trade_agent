"""
Paper Trading Example
Demonstrates how to use the paper trading system
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from modules.kotak_neo_auto_trader.infrastructure.broker_adapters import PaperTradingBrokerAdapter
from modules.kotak_neo_auto_trader.config.paper_trading_config import PaperTradingConfig
from modules.kotak_neo_auto_trader.infrastructure.simulation import PaperTradeReporter
from modules.kotak_neo_auto_trader.application.dto import OrderRequest
from modules.kotak_neo_auto_trader.application.use_cases import PlaceOrderUseCase
from modules.kotak_neo_auto_trader.domain import (
    OrderType, TransactionType, OrderVariety, ProductType, Exchange
)


def main():
    """Run paper trading example"""

    print("="*60)
    print("🎯 PAPER TRADING SYSTEM - EXAMPLE")
    print("="*60 + "\n")

    # 1. Create configuration
    print("📋 Step 1: Creating configuration...")
    config = PaperTradingConfig(
        initial_capital=100000.0,  # ₹1 lakh
        enable_slippage=True,
        enable_fees=True,
        price_source="mock",  # Use mock prices for demo
        storage_path="paper_trading/demo",
        enforce_market_hours=False  # Disable for demo
    )
    print(f"✅ Configuration created (Initial Capital: ₹{config.initial_capital:,.2f})\n")

    # 2. Initialize paper trading adapter
    print("📋 Step 2: Initializing paper trading adapter...")
    broker = PaperTradingBrokerAdapter(config)
    broker.connect()
    print("✅ Connected to paper trading system\n")

    # 3. Check initial balance
    print("📋 Step 3: Checking account balance...")
    balance = broker.get_available_balance()
    print(f"💰 Available balance: ₹{balance.amount:,.2f}\n")

    # 4. Place some BUY orders
    print("📋 Step 4: Placing BUY orders...\n")

    # Create use case
    place_order_uc = PlaceOrderUseCase(broker_gateway=broker)

    # Buy INFY
    print("  • Buying INFY...")
    order_req = OrderRequest.market_buy(
        symbol="INFY",
        quantity=10,
        variety=OrderVariety.REGULAR,
        product_type=ProductType.CNC
    )
    response = place_order_uc.execute(order_req)
    if response.success:
        print(f"    ✅ Order placed: {response.order_id}")
    else:
        print(f"    ❌ Order failed: {response.message}")

    # Buy TCS
    print("  • Buying TCS...")
    order_req = OrderRequest.market_buy(
        symbol="TCS",
        quantity=5,
        variety=OrderVariety.REGULAR,
        product_type=ProductType.CNC
    )
    response = place_order_uc.execute(order_req)
    if response.success:
        print(f"    ✅ Order placed: {response.order_id}")
    else:
        print(f"    ❌ Order failed: {response.message}")

    # Buy RELIANCE
    print("  • Buying RELIANCE...")
    order_req = OrderRequest.market_buy(
        symbol="RELIANCE",
        quantity=8,
        variety=OrderVariety.REGULAR,
        product_type=ProductType.CNC
    )
    response = place_order_uc.execute(order_req)
    if response.success:
        print(f"    ✅ Order placed: {response.order_id}\n")
    else:
        print(f"    ❌ Order failed: {response.message}\n")

    # 5. Check holdings
    print("📋 Step 5: Checking holdings...")
    holdings = broker.get_holdings()
    print(f"📊 Total holdings: {len(holdings)}")
    for holding in holdings:
        print(f"  • {holding.symbol}: {holding.quantity} shares @ ₹{holding.average_price.amount:.2f}")
    print()

    # 6. Check updated balance
    print("📋 Step 6: Checking updated balance...")
    balance = broker.get_available_balance()
    print(f"💰 Available balance: ₹{balance.amount:,.2f}\n")

    # 7. Place a SELL order
    print("📋 Step 7: Selling some INFY shares...")
    order_req = OrderRequest(
        symbol="INFY",
        quantity=5,
        order_type=OrderType.MARKET,
        transaction_type=TransactionType.SELL,
        variety=OrderVariety.REGULAR,
        product_type=ProductType.CNC
    )
    response = place_order_uc.execute(order_req)
    if response.success:
        print(f"✅ SELL order placed: {response.order_id}\n")
    else:
        print(f"❌ SELL order failed: {response.message}\n")

    # 8. Generate reports
    print("📋 Step 8: Generating reports...\n")
    reporter = PaperTradeReporter(broker.store)

    # Portfolio summary
    reporter.print_summary()

    # Holdings report
    reporter.print_holdings()

    # Recent orders
    reporter.print_recent_orders(limit=5)

    # 9. Export reports
    print("📋 Step 9: Exporting reports...")
    reporter.export_to_json("paper_trading/demo/report.json")
    print()

    # 10. Get account summary
    print("📋 Step 10: Getting comprehensive summary...")
    summary = broker.get_summary()
    print(f"✅ Account initialized on: {summary['account']['created_at']}")
    print(f"✅ Total orders: {summary['statistics']['total_orders']}")
    print(f"✅ Portfolio value: ₹{summary['portfolio']['portfolio_value']:,.2f}")
    print(f"✅ Total P&L: ₹{summary['portfolio']['total_pnl']:,.2f}")
    print()

    # Disconnect
    print("📋 Step 11: Disconnecting...")
    broker.disconnect()
    print("✅ Disconnected from paper trading system\n")

    print("="*60)
    print("✅ PAPER TRADING EXAMPLE COMPLETED")
    print("="*60)
    print(f"\n💡 Data saved to: {config.storage_path}/")
    print("💡 You can reconnect anytime and your data will be restored!")
    print()


if __name__ == "__main__":
    main()

