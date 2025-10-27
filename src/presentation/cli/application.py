"""
Application Entry Point

Wires up dependency injection and CLI commands.
"""

import argparse
import sys
from typing import Dict, Callable

from ...infrastructure.di_container import DIContainer
from .commands import AnalyzeCommand, BacktestCommand
from utils.logger import logger


class Application:
    """
    Main application class
    
    Orchestrates dependency injection, command registration, and CLI execution.
    """
    
    def __init__(self):
        """Initialize application with DI container"""
        self.container = DIContainer()
        self.commands: Dict[str, Callable] = {}
        self._register_commands()
    
    def _register_commands(self):
        """Register all available CLI commands"""
        # Analyze command
        analyze_cmd = AnalyzeCommand(
            bulk_analyze=self.container.bulk_analyze_use_case,
            send_alerts=self.container.send_alerts_use_case,
            scraper=self.container.chartink_scraper,
            formatter=self.container.telegram_formatter
        )
        self.commands['analyze'] = analyze_cmd
        
        # Backtest command
        backtest_cmd = BacktestCommand(
            scraper=self.container.chartink_scraper
        )
        self.commands['backtest'] = backtest_cmd
    
    def run(self, argv=None) -> int:
        """
        Run the application
        
        Args:
            argv: Command-line arguments (defaults to sys.argv)
            
        Returns:
            Exit code
        """
        parser = self._build_parser()
        args = parser.parse_args(argv)
        
        # Handle no command case
        if not hasattr(args, 'command') or not args.command:
            parser.print_help()
            return 1
        
        # Execute command
        command = self.commands.get(args.command)
        if not command:
            logger.error(f"Unknown command: {args.command}")
            return 1
        
        return command.execute(args)
    
    def _build_parser(self) -> argparse.ArgumentParser:
        """Build argument parser with all commands"""
        parser = argparse.ArgumentParser(
            description='Modular Trading Agent - Stock Analysis & Backtesting',
            formatter_class=argparse.RawDescriptionHelpFormatter
        )
        
        subparsers = parser.add_subparsers(dest='command', help='Available commands')
        
        # Analyze subcommand
        analyze_parser = subparsers.add_parser(
            'analyze',
            help='Analyze stocks and send alerts'
        )
        AnalyzeCommand.add_arguments(analyze_parser)
        
        # Backtest subcommand
        backtest_parser = subparsers.add_parser(
            'backtest',
            help='Run backtests on analysis strategies'
        )
        BacktestCommand.add_arguments(backtest_parser)
        
        return parser


def main():
    """Main entry point"""
    try:
        app = Application()
        sys.exit(app.run())
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        sys.exit(130)
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == '__main__':
    main()
