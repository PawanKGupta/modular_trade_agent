#!/usr/bin/env python3
"""
Service Conflict Detection and Prevention

This module provides utilities to detect and prevent multiple trading services
from running simultaneously, which causes JWT session conflicts.
"""

import os
import sys
import platform
import subprocess
from pathlib import Path
from typing import Optional, List

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from utils.logger import logger


def check_unified_service_running() -> bool:
    """
    Check if the unified trading service (run_trading_service.py) is running.
    
    Returns:
        True if unified service is running, False otherwise
    """
    try:
        if platform.system() == "Windows":
            # Check for Python processes running run_trading_service.py
            result = subprocess.run(
                ['tasklist', '/FI', 'IMAGENAME eq python.exe', '/FO', 'CSV'],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            if result.returncode == 0:
                output = result.stdout.lower()
                # Check if any Python process has run_trading_service in command line
                # We can't easily check command line args on Windows without WMI
                # So we check for the service name or process count
                # For now, check if there are multiple python processes (heuristic)
                python_count = output.count('python.exe')
                if python_count > 1:
                    # Could be unified service, but not definitive
                    # Better to check systemd/service status on Linux
                    pass
            
            # Check Windows service status
            result = subprocess.run(
                ['sc', 'query', 'TradeAgentUnified'],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            if result.returncode == 0 and 'RUNNING' in result.stdout:
                return True
                
        else:
            # Linux/Unix: Check systemd service
            result = subprocess.run(
                ['systemctl', 'is-active', 'tradeagent-unified.service'],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            if result.returncode == 0 and result.stdout.strip() == 'active':
                return True
            
            # Also check if process is running
            result = subprocess.run(
                ['pgrep', '-f', 'run_trading_service.py'],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            if result.returncode == 0:
                return True
                
    except Exception as e:
        logger.debug(f"Error checking unified service: {e}")
    
    return False


def check_old_services_running() -> List[str]:
    """
    Check if any old individual services are running.
    
    Returns:
        List of running old service names
    """
    running_services = []
    
    try:
        if platform.system() == "Windows":
            # Check Windows services
            old_services = [
                'ModularTradeAgent_Sell',
                'ModularTradeAgent_Main',
                'ModularTradeAgent_Monitor',
                'ModularTradeAgent_EOD'
            ]
            
            for service_name in old_services:
                result = subprocess.run(
                    ['sc', 'query', service_name],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                
                if result.returncode == 0 and 'RUNNING' in result.stdout:
                    running_services.append(service_name)
                    
        else:
            # Check Linux systemd services
            old_services = [
                'tradeagent-sell.service',
                'tradeagent-autotrade.service',
                'tradeagent-monitor.service',
                'tradeagent-eod.service'
            ]
            
            for service_name in old_services:
                result = subprocess.run(
                    ['systemctl', 'is-active', service_name],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                
                if result.returncode == 0 and result.stdout.strip() == 'active':
                    running_services.append(service_name)
            
            # Also check for running processes
            for script in ['run_sell_orders.py', 'run_auto_trade.py', 
                          'run_position_monitor.py', 'run_eod_cleanup.py']:
                result = subprocess.run(
                    ['pgrep', '-f', script],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                
                if result.returncode == 0:
                    running_services.append(f"Process: {script}")
                    
    except Exception as e:
        logger.debug(f"Error checking old services: {e}")
    
    return running_services


def stop_old_services_automatically() -> List[str]:
    """
    Automatically stop old services when unified service starts.
    
    Returns:
        List of services that were stopped
    """
    stopped = []
    
    try:
        if platform.system() == "Windows":
            old_services = [
                'ModularTradeAgent_Sell',
                'ModularTradeAgent_Main',
                'ModularTradeAgent_Monitor',
                'ModularTradeAgent_EOD'
            ]
            
            for service in old_services:
                try:
                    result = subprocess.run(
                        ['sc', 'stop', service],
                        capture_output=True,
                        text=True,
                        timeout=10
                    )
                    
                    if result.returncode == 0:
                        logger.info(f"✓ Automatically stopped {service}")
                        stopped.append(service)
                    elif 'does not exist' in result.stdout or 'STOPPED' in result.stdout:
                        # Service doesn't exist or already stopped - that's fine
                        pass
                except Exception as e:
                    logger.debug(f"Could not stop {service}: {e}")
                    
        else:
            # Linux: Stop systemd services
            old_services = [
                'tradeagent-sell.service',
                'tradeagent-autotrade.service',
                'tradeagent-monitor.service',
                'tradeagent-eod.service'
            ]
            
            for service in old_services:
                try:
                    result = subprocess.run(
                        ['systemctl', 'stop', service],
                        capture_output=True,
                        text=True,
                        timeout=10
                    )
                    
                    if result.returncode == 0:
                        logger.info(f"✓ Automatically stopped {service}")
                        stopped.append(service)
                    elif 'not found' in result.stderr.lower():
                        # Service doesn't exist - that's fine
                        pass
                except Exception as e:
                    logger.debug(f"Could not stop {service}: {e}")
                    
    except Exception as e:
        logger.warning(f"Error stopping old services: {e}")
    
    return stopped


def prevent_service_conflict(script_name: str, is_unified: bool = False, auto_stop: bool = True) -> bool:
    """
    Check for service conflicts and prevent execution if conflicts detected.
    
    Args:
        script_name: Name of the script being run (for logging)
        is_unified: True if this is the unified service, False if old service
        auto_stop: If True and unified service, automatically stop old services
        
    Returns:
        True if safe to proceed, False if conflict detected
    """
    if is_unified:
        # Unified service: Check if old services are running
        old_services = check_old_services_running()
        
        if old_services:
            if auto_stop:
                # Automatically stop old services
                logger.warning("=" * 80)
                logger.warning("SERVICE CONFLICT DETECTED - AUTO-RESOLVING")
                logger.warning("=" * 80)
                logger.warning(f"Found {len(old_services)} old service(s) running:")
                for service in old_services:
                    logger.warning(f"  - {service}")
                logger.warning("")
                logger.warning("Automatically stopping old services to prevent conflicts...")
                logger.warning("")
                
                stopped = stop_old_services_automatically()
                
                if stopped:
                    logger.info("")
                    logger.info(f"✓ Successfully stopped {len(stopped)} old service(s)")
                    logger.info("")
                    logger.info("💡 RECOMMENDATION:")
                    logger.info("   Disable old services to prevent them from auto-starting:")
                    if platform.system() == "Windows":
                        logger.info("     sc config ModularTradeAgent_Sell start= disabled")
                        logger.info("     (Repeat for other services)")
                        logger.info("")
                        logger.info("   Or run: python scripts/migrate_to_unified_service.py")
                    else:
                        logger.info("     sudo systemctl disable tradeagent-sell.timer")
                        logger.info("     sudo systemctl disable tradeagent-autotrade.timer")
                        logger.info("     sudo systemctl disable tradeagent-monitor.timer")
                        logger.info("     sudo systemctl disable tradeagent-eod.timer")
                        logger.info("")
                        logger.info("   Or run: sudo python scripts/migrate_to_unified_service.py")
                    logger.info("=" * 80)
                else:
                    logger.warning("⚠ Could not automatically stop old services")
                    logger.warning("Please stop them manually before starting unified service")
                    logger.error("=" * 80)
                    return False
            else:
                # Just warn, don't auto-stop
                logger.error("=" * 80)
                logger.error("SERVICE CONFLICT DETECTED!")
                logger.error("=" * 80)
                logger.error(f"The unified trading service ({script_name}) cannot run")
                logger.error("while old individual services are active:")
                for service in old_services:
                    logger.error(f"  - {service}")
                logger.error("")
                logger.error("SOLUTION:")
                logger.error("  1. Stop all old services:")
                if platform.system() == "Windows":
                    logger.error("     sc stop ModularTradeAgent_Sell")
                    logger.error("     sc stop ModularTradeAgent_Main")
                    logger.error("     sc stop ModularTradeAgent_Monitor")
                    logger.error("     sc stop ModularTradeAgent_EOD")
                else:
                    logger.error("     sudo systemctl stop tradeagent-sell.service")
                    logger.error("     sudo systemctl stop tradeagent-autotrade.service")
                    logger.error("     sudo systemctl stop tradeagent-monitor.service")
                    logger.error("     sudo systemctl stop tradeagent-eod.service")
                logger.error("")
                logger.error("  2. Disable old services to prevent auto-start:")
                if platform.system() == "Windows":
                    logger.error("     sc config ModularTradeAgent_Sell start= disabled")
                    logger.error("     (Repeat for other services)")
                else:
                    logger.error("     sudo systemctl disable tradeagent-sell.timer")
                    logger.error("     sudo systemctl disable tradeagent-autotrade.timer")
                    logger.error("     sudo systemctl disable tradeagent-monitor.timer")
                    logger.error("     sudo systemctl disable tradeagent-eod.timer")
                logger.error("")
                logger.error("  3. Then restart the unified service")
                logger.error("=" * 80)
                return False
            
    else:
        # Old service: Check if unified service is running
        if check_unified_service_running():
            logger.error("=" * 80)
            logger.error("SERVICE CONFLICT DETECTED!")
            logger.error("=" * 80)
            logger.error(f"The old service ({script_name}) cannot run")
            logger.error("while the unified trading service is active.")
            logger.error("")
            logger.error("SOLUTION:")
            logger.error("  The unified service (run_trading_service.py) handles")
            logger.error("  all trading tasks automatically. You should:")
            logger.error("")
            logger.error("  1. Stop this old service")
            logger.error("  2. Use only the unified service for production")
            logger.error("")
            logger.error("  If you need to run this script manually for testing,")
            logger.error("  first stop the unified service:")
            if platform.system() == "Windows":
                logger.error("     sc stop TradeAgentUnified")
            else:
                logger.error("     sudo systemctl stop tradeagent-unified.service")
            logger.error("=" * 80)
            return False
    
    return True

