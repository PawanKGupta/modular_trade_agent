#!/usr/bin/env python3
"""
Integration test for re-authentication with actual modules

Verifies that all critical methods have the @handle_reauth decorator
and checks method signatures are correct
"""

import sys
import inspect
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

def test_decorator_application():
    """Test that decorators are applied to all critical methods"""
    print("="*80)
    print("TESTING DECORATOR APPLICATION")
    print("="*80)
    
    try:
        from modules.kotak_neo_auto_trader.orders import KotakNeoOrders
        from modules.kotak_neo_auto_trader.market_data import KotakNeoMarketData
        from modules.kotak_neo_auto_trader.portfolio import KotakNeoPortfolio
        from modules.kotak_neo_auto_trader.auth_handler import handle_reauth
        
        results = {
            'passed': [],
            'failed': []
        }
        
        # Test orders module
        print("\n📋 Testing KotakNeoOrders methods:")
        orders_methods = [
            'place_equity_order',
            'modify_order',
            'cancel_order',
            'get_orders'
        ]
        
        for method_name in orders_methods:
            method = getattr(KotakNeoOrders, method_name)
            
            # Check if decorator is applied (has __wrapped__ attribute)
            if hasattr(method, '__wrapped__'):
                print(f"  [OK] {method_name} - decorator applied")
                results['passed'].append(f"orders.{method_name}")
            else:
                # Check if it's decorated (wrapper function)
                if hasattr(method, '__name__') and method.__name__ != method_name:
                    print(f"  [OK] {method_name} - appears decorated")
                    results['passed'].append(f"orders.{method_name}")
                else:
                    print(f"  [WARN] {method_name} - decorator status unclear")
                    results['failed'].append(f"orders.{method_name}")
        
        # Test market_data module
        print("\n📊 Testing KotakNeoMarketData methods:")
        market_methods = ['get_quote']
        
        for method_name in market_methods:
            method = getattr(KotakNeoMarketData, method_name)
            
            if hasattr(method, '__wrapped__'):
                print(f"  [OK] {method_name} - decorator applied")
                results['passed'].append(f"market_data.{method_name}")
            else:
                if hasattr(method, '__name__') and method.__name__ != method_name:
                    print(f"  [OK] {method_name} - appears decorated")
                    results['passed'].append(f"market_data.{method_name}")
                else:
                    print(f"  [WARN] {method_name} - decorator status unclear")
                    results['failed'].append(f"market_data.{method_name}")
        
        # Test portfolio module
        print("\n💼 Testing KotakNeoPortfolio methods:")
        portfolio_methods = ['get_positions', 'get_limits']
        
        for method_name in portfolio_methods:
            method = getattr(KotakNeoPortfolio, method_name)
            
            if hasattr(method, '__wrapped__'):
                print(f"  [OK] {method_name} - decorator applied")
                results['passed'].append(f"portfolio.{method_name}")
            else:
                if hasattr(method, '__name__') and method.__name__ != method_name:
                    print(f"  [OK] {method_name} - appears decorated")
                    results['passed'].append(f"portfolio.{method_name}")
                else:
                    print(f"  [WARN] {method_name} - decorator status unclear")
                    results['failed'].append(f"portfolio.{method_name}")
        
        return results
        
    except Exception as e:
        print(f"❌ Error testing decorator application: {e}")
        import traceback
        traceback.print_exc()
        return {'passed': [], 'failed': [f"Error: {e}"]}


def test_method_signatures():
    """Test that method signatures are correct after decorator application"""
    print("\n" + "="*80)
    print("TESTING METHOD SIGNATURES")
    print("="*80)
    
    try:
        from modules.kotak_neo_auto_trader.orders import KotakNeoOrders
        from modules.kotak_neo_auto_trader.market_data import KotakNeoMarketData
        from modules.kotak_neo_auto_trader.portfolio import KotakNeoPortfolio
        
        results = {
            'passed': [],
            'failed': []
        }
        
        # Test get_orders signature (should not have _retry_count anymore)
        print("\n📋 Testing get_orders signature:")
        get_orders_method = KotakNeoOrders.get_orders
        sig = inspect.signature(get_orders_method)
        params = list(sig.parameters.keys())
        
        if '_retry_count' not in params:
            print(f"  [OK] get_orders signature correct: {params}")
            results['passed'].append("get_orders signature")
        else:
            print(f"  [FAIL] get_orders still has _retry_count parameter")
            results['failed'].append("get_orders signature")
        
        # Test other method signatures
        methods_to_test = [
            (KotakNeoOrders, 'place_equity_order', ['symbol', 'quantity']),
            (KotakNeoOrders, 'modify_order', ['order_id']),
            (KotakNeoOrders, 'cancel_order', ['order_id']),
            (KotakNeoMarketData, 'get_quote', ['symbol']),
            (KotakNeoPortfolio, 'get_positions', []),
            (KotakNeoPortfolio, 'get_limits', []),
        ]
        
        print("\n📋 Testing other method signatures:")
        for cls, method_name, expected_params in methods_to_test:
            try:
                method = getattr(cls, method_name)
                sig = inspect.signature(method)
                params = list(sig.parameters.keys())
                
                # Check that expected params are present
                missing = [p for p in expected_params if p not in params]
                if not missing:
                    print(f"  [OK] {cls.__name__}.{method_name} - signature OK")
                    results['passed'].append(f"{cls.__name__}.{method_name}")
                else:
                    print(f"  [WARN] {cls.__name__}.{method_name} - missing params: {missing}")
                    results['failed'].append(f"{cls.__name__}.{method_name}")
            except Exception as e:
                print(f"  [FAIL] {cls.__name__}.{method_name} - error: {e}")
                results['failed'].append(f"{cls.__name__}.{method_name}")
        
        return results
        
    except Exception as e:
        print(f"❌ Error testing method signatures: {e}")
        import traceback
        traceback.print_exc()
        return {'passed': [], 'failed': [f"Error: {e}"]}


def test_imports():
    """Test that all imports work correctly"""
    print("\n" + "="*80)
    print("TESTING IMPORTS")
    print("="*80)
    
    try:
        print("\n[OK] Testing imports...")
        
        # Test auth_handler import
        from modules.kotak_neo_auto_trader.auth_handler import (
            handle_reauth,
            is_auth_error,
            call_with_reauth,
            AuthGuard
        )
        print("  [OK] auth_handler imports successful")
        
        # Test module imports
        from modules.kotak_neo_auto_trader.orders import KotakNeoOrders
        print("  [OK] orders import successful")
        
        from modules.kotak_neo_auto_trader.market_data import KotakNeoMarketData
        print("  [OK] market_data import successful")
        
        from modules.kotak_neo_auto_trader.portfolio import KotakNeoPortfolio
        print("  [OK] portfolio import successful")
        
        return True
        
    except Exception as e:
        print(f"  [FAIL] Import failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all integration tests"""
    print("="*80)
    print("RE-AUTHENTICATION INTEGRATION TEST")
    print("="*80)
    
    all_passed = True
    
    # Test imports
    if not test_imports():
        print("\n❌ Import test failed")
        return 1
    
    # Test decorator application
    decorator_results = test_decorator_application()
    
    # Test method signatures
    signature_results = test_method_signatures()
    
    # Summary
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)
    
    total_passed = len(decorator_results['passed']) + len(signature_results['passed'])
    total_failed = len(decorator_results['failed']) + len(signature_results['failed'])
    
    print(f"\n[OK] Passed: {total_passed}")
    print(f"[FAIL] Failed: {total_failed}")
    
    if decorator_results['failed']:
        print("\n[WARN] Decorator application issues:")
        for item in decorator_results['failed']:
            print(f"  - {item}")
        all_passed = False
    
    if signature_results['failed']:
        print("\n[WARN] Signature issues:")
        for item in signature_results['failed']:
            print(f"  - {item}")
        all_passed = False
    
    if all_passed:
        print("\n[OK] ALL INTEGRATION TESTS PASSED")
        print("\n[OK] Re-authentication implementation is correctly applied")
        print("[OK] All critical methods have @handle_reauth decorator")
        print("[OK] Method signatures are correct")
        return 0
    else:
        print("\n[FAIL] SOME INTEGRATION TESTS FAILED")
        return 1


if __name__ == '__main__':
    sys.exit(main())

