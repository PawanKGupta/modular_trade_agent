#!/usr/bin/env python3
"""
Symbol Utility Functions
Centralized symbol normalization and transformation utilities
"""

from typing import Optional


def normalize_symbol(symbol: str) -> str:
    """
    Normalize symbol to uppercase.
    
    Args:
        symbol: Symbol string (e.g., 'reliance', 'DALBHARAT-EQ')
        
    Returns:
        Uppercase symbol
    """
    return symbol.strip().upper() if symbol else ""


def extract_base_symbol(symbol: str) -> str:
    """
    Extract base symbol by removing segment suffix.
    
    Examples:
        'DALBHARAT-EQ' -> 'DALBHARAT'
        'RELIANCE-BL' -> 'RELIANCE'
        'TCS' -> 'TCS'
    
    Args:
        symbol: Full trading symbol (e.g., 'DALBHARAT-EQ')
        
    Returns:
        Base symbol without segment suffix
    """
    return normalize_symbol(symbol).split('-')[0]


def extract_ticker_base(ticker: str) -> str:
    """
    Extract base symbol from ticker format.
    
    Examples:
        'RELIANCE.NS' -> 'RELIANCE'
        'TCS.BO' -> 'TCS'
        'DALBHARAT' -> 'DALBHARAT'
    
    Args:
        ticker: Ticker string (e.g., 'RELIANCE.NS')
        
    Returns:
        Base symbol without exchange suffix
    """
    return normalize_symbol(ticker).replace('.NS', '').replace('.BO', '')


def get_lookup_symbol(broker_symbol: Optional[str], base_symbol: str) -> str:
    """
    Get the appropriate symbol for lookup.
    
    Prioritizes broker_symbol (full trading symbol) if available,
    otherwise falls back to base_symbol.
    
    Args:
        broker_symbol: Full trading symbol (e.g., 'DALBHARAT-EQ') or None
        base_symbol: Base symbol (e.g., 'DALBHARAT')
        
    Returns:
        Symbol to use for lookup
    """
    if broker_symbol:
        return normalize_symbol(broker_symbol)
    return normalize_symbol(base_symbol)

