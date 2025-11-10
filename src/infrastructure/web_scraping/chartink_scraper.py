"""
ChartInk Scraper

Wraps existing scrapping.py functionality for fetching stock lists.
"""

from typing import List, Optional

# Import existing implementation
from core.scrapping import get_stock_list
from utils.logger import logger


class ChartInkScraper:
    """
    ChartInk web scraper for fetching stock lists
    
    Wraps existing scrapping.py functionality.
    """
    
    def __init__(self):
        """Initialize ChartInk scraper"""
        logger.debug("ChartInkScraper initialized")
    
    def get_stocks(self) -> List[str]:
        """
        Get list of stocks from ChartInk screener
        
        Returns:
            List of stock symbols (without .NS suffix)
        """
        try:
            stocks_str = get_stock_list()
            
            if stocks_str is None or stocks_str.strip() == "":
                logger.error("Stock scraping failed, no stocks returned")
                return []
            
            # Parse comma-separated list
            stocks = [s.strip().upper() for s in stocks_str.split(",") if s.strip()]
            
            logger.info(f"Scraped {len(stocks)} stocks from ChartInk")
            return stocks
            
        except Exception as e:
            logger.error(f"Failed to scrape stocks from ChartInk: {e}")
            return []
    
    def get_stocks_with_suffix(self, suffix: str = ".NS") -> List[str]:
        """
        Get list of stocks with exchange suffix added
        
        Args:
            suffix: Exchange suffix to add (default: .NS for NSE)
            
        Returns:
            List of stock symbols with suffix
        """
        stocks = self.get_stocks()
        return [f"{stock}{suffix}" for stock in stocks]
    
    def is_available(self) -> bool:
        """
        Check if scraper is available/working
        
        Returns:
            True if scraper can fetch stocks
        """
        try:
            stocks = self.get_stocks()
            return len(stocks) > 0
        except Exception:
            return False
