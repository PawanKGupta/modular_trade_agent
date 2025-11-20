"""
Telegram Notifier

Implements NotificationService interface using Telegram Bot API.
Wraps existing telegram.py functionality.
"""

from typing import List

# Import domain interface
from ...domain.interfaces.notification_service import NotificationService, NotificationError
from ...domain.entities.analysis_result import AnalysisResult

# Import existing implementation
from core.telegram import send_telegram
from utils.logger import logger


class TelegramNotifier(NotificationService):
    """
    Telegram implementation of NotificationService interface

    Wraps existing telegram.py functionality with clean interface.
    """

    def __init__(self):
        """Initialize Telegram notifier"""
        logger.debug("TelegramNotifier initialized")

    def send_alert(self, message: str, **kwargs) -> bool:
        """
        Send a notification alert

        Args:
            message: Message content to send
            **kwargs: Additional parameters (not used currently)

        Returns:
            True if sent successfully, False otherwise
        """
        try:
            send_telegram(message)
            logger.info("Telegram alert sent successfully")
            return True

        except Exception as e:
            logger.error(f"Failed to send Telegram alert: {e}")
            return False

    def send_analysis_results(self, results: List[AnalysisResult], **kwargs) -> bool:
        """
        Send formatted analysis results

        Args:
            results: List of analysis results to send
            **kwargs: Additional formatting options

        Returns:
            True if sent successfully
        """
        try:
            # Format results into message
            message = self._format_results_message(results)

            # Send via Telegram
            return self.send_alert(message)

        except Exception as e:
            logger.error(f"Failed to send analysis results: {e}")
            return False

    def send_error_alert(self, error_message: str, **kwargs) -> bool:
        """
        Send error notification

        Args:
            error_message: Error description
            **kwargs: Additional context

        Returns:
            True if sent successfully
        """
        try:
            formatted_message = f"[WARN]? *Error Alert*\n\n{error_message}"
            return self.send_alert(formatted_message)

        except Exception as e:
            logger.error(f"Failed to send error alert: {e}")
            return False

    def is_available(self) -> bool:
        """
        Check if notification service is available

        Returns:
            True if service can send notifications
        """
        try:
            # Check if Telegram credentials are configured
            from config.settings import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID

            return bool(TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID)
        except Exception:
            return False

    def test_connection(self) -> bool:
        """
        Test notification service connectivity

        Returns:
            True if connection is working
        """
        try:
            test_message = "? Test message from TradingAgent"
            return self.send_alert(test_message)
        except Exception as e:
            logger.error(f"Telegram connection test failed: {e}")
            return False

    def _format_results_message(self, results: List[AnalysisResult]) -> str:
        """Format analysis results into Telegram message"""
        # This is a simplified version - actual formatting should be more sophisticated
        buyable = [r for r in results if r.is_buyable()]

        if not buyable:
            return "*No buy candidates found today*"

        message = f"*Found {len(buyable)} buy candidates*\n\n"

        for result in buyable[:10]:  # Limit to 10
            message += f"? {result.ticker}: {result.get_verdict()}\n"

        return message
