"""
NotificationService Interface - Domain Layer

Abstract interface for sending notifications/alerts.
"""

from abc import ABC, abstractmethod
from typing import List, Optional
from ..entities.analysis_result import AnalysisResult


class NotificationService(ABC):
    """
    Interface for sending notifications
    
    This abstraction allows using different notification channels
    (Telegram, Email, SMS, Webhook, etc.) without changing business logic.
    """
    
    @abstractmethod
    def send_alert(self, message: str, **kwargs) -> bool:
        """
        Send a notification alert
        
        Args:
            message: Message content to send
            **kwargs: Additional parameters (priority, formatting, etc.)
            
        Returns:
            True if sent successfully, False otherwise
        """
        pass
    
    @abstractmethod
    def send_analysis_results(
        self,
        results: List[AnalysisResult],
        **kwargs
    ) -> bool:
        """
        Send formatted analysis results
        
        Args:
            results: List of analysis results to send
            **kwargs: Additional formatting options
            
        Returns:
            True if sent successfully
        """
        pass
    
    @abstractmethod
    def send_error_alert(self, error_message: str, **kwargs) -> bool:
        """
        Send error notification
        
        Args:
            error_message: Error description
            **kwargs: Additional context
            
        Returns:
            True if sent successfully
        """
        pass
    
    @abstractmethod
    def is_available(self) -> bool:
        """
        Check if notification service is available
        
        Returns:
            True if service can send notifications
        """
        pass
    
    @abstractmethod
    def test_connection(self) -> bool:
        """
        Test notification service connectivity
        
        Returns:
            True if connection is working
        """
        pass


class NotificationError(Exception):
    """Exception raised when notification sending fails"""
    pass
