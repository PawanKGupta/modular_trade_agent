"""
CSV Repository

Wraps existing csv_exporter.py functionality for data persistence.
"""

from typing import List, Dict, Any, Optional
from datetime import datetime

# Import existing implementation
from core.csv_exporter import CSVExporter
from utils.logger import logger


class CSVRepository:
    """
    CSV-based repository for persisting analysis results
    
    Wraps existing csv_exporter.py functionality.
    """
    
    def __init__(self):
        """Initialize CSV repository"""
        self.exporter = CSVExporter()
        logger.debug("CSVRepository initialized")
    
    def save_analysis(self, ticker: str, analysis_data: Dict[str, Any]) -> bool:
        """
        Save individual analysis result
        
        Args:
            ticker: Stock symbol
            analysis_data: Analysis result dictionary
            
        Returns:
            True if saved successfully
        """
        try:
            self.exporter.export_single_analysis(ticker, analysis_data)
            logger.debug(f"Saved analysis for {ticker}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to save analysis for {ticker}: {e}")
            return False
    
    def save_bulk_analysis(
        self,
        results: List[Dict[str, Any]],
        timestamp: Optional[datetime] = None
    ) -> Optional[str]:
        """
        Save bulk analysis results
        
        Args:
            results: List of analysis result dictionaries
            timestamp: Optional timestamp for filename
            
        Returns:
            Path to saved file, or None if failed
        """
        try:
            filepath = self.exporter.export_bulk_analysis(results, timestamp)
            logger.info(f"Saved bulk analysis to {filepath}")
            return filepath
            
        except Exception as e:
            logger.error(f"Failed to save bulk analysis: {e}")
            return None
    
    def append_to_master(self, analysis_data: Dict[str, Any]) -> bool:
        """
        Append analysis to master CSV file
        
        Args:
            analysis_data: Analysis result dictionary
            
        Returns:
            True if appended successfully
        """
        try:
            self.exporter.append_to_master(analysis_data)
            logger.debug("Appended to master CSV")
            return True
            
        except Exception as e:
            logger.error(f"Failed to append to master CSV: {e}")
            return False
