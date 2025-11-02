#!/usr/bin/env python3
"""
Modular Trade Agent - Automatic Setup Installer
This script handles the complete installation:
1. Extracts Python and dependencies (already bundled)
2. Guides user through .env configuration
3. Installs Windows services
4. Starts the services
"""

import os
import sys
import shutil
import subprocess
from pathlib import Path
import winreg
import ctypes

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))
from utils.version import Version, get_installed_version, get_package_version, save_version, format_version_info

# GUI imports
try:
    import tkinter as tk
    from tkinter import ttk, messagebox, scrolledtext
    HAS_GUI = True
except ImportError:
    HAS_GUI = False
    print("Warning: GUI not available, using console mode")


class TradeAgentInstaller:
    """Automated installer for Modular Trade Agent"""
    
    def __init__(self):
        self.install_dir = Path(os.environ.get('PROGRAMDATA', 'C:\\ProgramData')) / 'ModularTradeAgent'
        self.env_config = {}
        self.services = []
        self.installer_version = get_package_version() or Version("25.4.0")
        self.installed_version = get_installed_version(self.install_dir)
        
    def is_admin(self):
        """Check if running with admin privileges"""
        try:
            return ctypes.windll.shell32.IsUserAnAdmin()
        except:
            return False
    
    def request_admin(self):
        """Request admin elevation"""
        if not self.is_admin():
            # Re-run the script with admin rights
            ctypes.windll.shell32.ShellExecuteW(
                None, "runas", sys.executable, " ".join(sys.argv), None, 1
            )
            sys.exit()
    
    def create_installation_directory(self):
        """Create installation directory structure"""
        print("Creating installation directory...")
        
        dirs_to_create = [
            self.install_dir,
            self.install_dir / 'data',
            self.install_dir / 'logs',
            self.install_dir / 'config'
        ]
        
        for dir_path in dirs_to_create:
            dir_path.mkdir(parents=True, exist_ok=True)
            print(f"  ✓ Created: {dir_path}")
    
    def extract_application_files(self):
        """Extract bundled application files to installation directory"""
        print("\nExtracting application files...")
        
        try:
            # Get the bundled portable_package directory
            if getattr(sys, 'frozen', False):
                # Running as compiled executable
                bundle_dir = Path(sys._MEIPASS) / 'portable_package'
            else:
                # Running as script (development)
                bundle_dir = Path(__file__).parent.parent / 'portable_package'
            
            if not bundle_dir.exists():
                print(f"  ! Bundle directory not found: {bundle_dir}")
                return False
            
            # Copy Python
            python_src = bundle_dir / 'python'
            python_dst = self.install_dir / 'python'
            if python_src.exists():
                shutil.copytree(python_src, python_dst, dirs_exist_ok=True)
                print(f"  ✓ Extracted Python runtime")
            
            # Copy TradingAgent
            agent_src = bundle_dir / 'TradingAgent'
            agent_dst = self.install_dir / 'TradingAgent'
            if agent_src.exists():
                shutil.copytree(agent_src, agent_dst, dirs_exist_ok=True)
                print(f"  ✓ Extracted Trading Agent application")
            
            # Copy launcher scripts
            for bat_file in bundle_dir.glob('*.bat'):
                shutil.copy2(bat_file, self.install_dir / bat_file.name)
            
            # Copy README
            readme = bundle_dir / 'README.md'
            if readme.exists():
                shutil.copy2(readme, self.install_dir / 'README.md')
            
            return True
            
        except Exception as e:
            print(f"  ✗ Failed to extract files: {e}")
            return False
    
    def collect_env_configuration(self):
        """Collect environment configuration from user"""
        if HAS_GUI:
            return self._collect_env_gui()
        else:
            return self._collect_env_console()
    
    def _collect_env_console(self):
        """Console-based configuration collection"""
        print("\n" + "="*60)
        print("CONFIGURATION SETUP")
        print("="*60)
        print("\nPlease provide your Kotak Neo credentials:")
        print("(Press Enter to skip optional fields)\n")
        
        fields = [
            ("KOTAK_NEO_CONSUMER_KEY", "Consumer Key", True),
            ("KOTAK_NEO_CONSUMER_SECRET", "Consumer Secret", True),
            ("KOTAK_NEO_MOBILE_NUMBER", "Mobile Number", True),
            ("KOTAK_NEO_PASSWORD", "Password", True),
            ("KOTAK_NEO_MPIN", "MPIN (6 digits)", True),
            ("TELEGRAM_BOT_TOKEN", "Telegram Bot Token (optional)", False),
            ("TELEGRAM_CHAT_ID", "Telegram Chat ID (optional)", False),
        ]
        
        for var_name, display_name, required in fields:
            while True:
                value = input(f"{display_name}: ").strip()
                if value or not required:
                    if value:
                        self.env_config[var_name] = value
                    break
                else:
                    print(f"  ✗ {display_name} is required!")
        
        return True
    
    def _collect_env_gui(self):
        """GUI-based configuration collection"""
        root = tk.Tk()
        root.title("Modular Trade Agent - Configuration")
        root.geometry("500x450")
        root.resizable(False, False)
        
        # Header
        header = tk.Label(root, text="Trading Agent Configuration", 
                         font=("Arial", 14, "bold"), pady=10)
        header.pack()
        
        tk.Label(root, text="Enter your Kotak Neo credentials:", 
                font=("Arial", 10)).pack()
        
        # Scrollable frame for inputs
        canvas = tk.Canvas(root)
        scrollbar = ttk.Scrollbar(root, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        # Input fields
        fields = [
            ("KOTAK_NEO_CONSUMER_KEY", "Consumer Key *"),
            ("KOTAK_NEO_CONSUMER_SECRET", "Consumer Secret *"),
            ("KOTAK_NEO_MOBILE_NUMBER", "Mobile Number *"),
            ("KOTAK_NEO_PASSWORD", "Password *"),
            ("KOTAK_NEO_MPIN", "MPIN (6 digits) *"),
            ("TELEGRAM_BOT_TOKEN", "Telegram Bot Token"),
            ("TELEGRAM_CHAT_ID", "Telegram Chat ID"),
        ]
        
        entries = {}
        for var_name, label_text in fields:
            frame = ttk.Frame(scrollable_frame)
            frame.pack(fill='x', padx=20, pady=5)
            
            label = ttk.Label(frame, text=label_text, width=25, anchor='w')
            label.pack(side='left')
            
            entry = ttk.Entry(frame, width=30, show='*' if 'PASSWORD' in var_name or 'MPIN' in var_name else '')
            entry.pack(side='right', expand=True, fill='x')
            entries[var_name] = entry
        
        canvas.pack(side="left", fill="both", expand=True, padx=10)
        scrollbar.pack(side="right", fill="y")
        
        # Buttons
        button_frame = ttk.Frame(root)
        button_frame.pack(pady=10)
        
        def on_submit():
            # Validate required fields
            required_fields = [
                "KOTAK_NEO_CONSUMER_KEY",
                "KOTAK_NEO_CONSUMER_SECRET",
                "KOTAK_NEO_MOBILE_NUMBER",
                "KOTAK_NEO_PASSWORD",
                "KOTAK_NEO_MPIN"
            ]
            
            for field in required_fields:
                value = entries[field].get().strip()
                if not value:
                    messagebox.showerror("Error", f"{field.replace('_', ' ')} is required!")
                    return
            
            # Collect all values
            for var_name, entry in entries.items():
                value = entry.get().strip()
                if value:
                    self.env_config[var_name] = value
            
            root.quit()
            root.destroy()
        
        def on_cancel():
            if messagebox.askyesno("Cancel", "Are you sure you want to cancel installation?"):
                sys.exit(0)
        
        ttk.Button(button_frame, text="Install", command=on_submit, width=15).pack(side='left', padx=5)
        ttk.Button(button_frame, text="Cancel", command=on_cancel, width=15).pack(side='left', padx=5)
        
        root.mainloop()
        return True
    
    def save_env_file(self):
        """Save .env configuration file"""
        env_path = self.install_dir / 'kotak_neo.env'
        
        print(f"\nSaving configuration to {env_path}...")
        
        with open(env_path, 'w') as f:
            f.write("# Modular Trade Agent Configuration\n")
            f.write(f"# Generated: {Path(__file__).name}\n\n")
            
            for key, value in self.env_config.items():
                f.write(f"{key}={value}\n")
        
        print("  ✓ Configuration saved")
    
    def install_services(self):
        """Install Windows services using NSSM"""
        print("\nInstalling Windows services...")
        
        # Check if NSSM is available
        nssm_path = self._get_nssm_path()
        if not nssm_path:
            print("  ! NSSM not found, skipping service installation")
            print("  You can run the agent manually using RUN_AGENT.bat")
            return False
        
        python_exe = sys.executable
        base_dir = self.install_dir / 'TradingAgent' / 'modules' / 'kotak_neo_auto_trader'
        
        # Define all services to install
        services_config = [
            {
                'name': 'ModularTradeAgent_Main',
                'script': base_dir / 'run_auto_trade.py',
                'description': 'Main Auto Trading Engine - Places orders and manages positions',
                'start': 'SERVICE_DEMAND_START'  # Manual start
            },
            {
                'name': 'ModularTradeAgent_Monitor',
                'script': base_dir / 'run_position_monitor.py',
                'description': 'Position Monitor - Real-time monitoring and alerts',
                'start': 'SERVICE_DEMAND_START'  # Manual start
            },
            {
                'name': 'ModularTradeAgent_EOD',
                'script': base_dir / 'run_eod_cleanup.py',
                'description': 'End-of-Day Cleanup - Reconciliation and daily summary',
                'start': 'SERVICE_DEMAND_START'  # Manual start
            },
            {
                'name': 'ModularTradeAgent_Sell',
                'script': base_dir / 'run_sell_orders.py',
                'description': 'Sell Order Manager - EMA9 target tracking and execution',
                'start': 'SERVICE_DEMAND_START'  # Manual start
            },
        ]
        
        installed_count = 0
        failed_count = 0
        
        for service_config in services_config:
            service_name = service_config['name']
            script_path = service_config['script']
            
            # Check if script exists
            if not script_path.exists():
                print(f"  ! Script not found: {script_path.name} - skipping")
                continue
            
            try:
                # Install service
                subprocess.run([
                    nssm_path, "install", service_name, python_exe, str(script_path)
                ], check=True, capture_output=True, text=True)
                
                # Configure service
                subprocess.run([
                    nssm_path, "set", service_name, "AppDirectory", str(self.install_dir / 'TradingAgent')
                ], check=True, capture_output=True, text=True)
                
                subprocess.run([
                    nssm_path, "set", service_name, "Description", service_config['description']
                ], check=True, capture_output=True, text=True)
                
                subprocess.run([
                    nssm_path, "set", service_name, "Start", service_config['start']
                ], check=True, capture_output=True, text=True)
                
                # Set log files
                log_dir = self.install_dir / 'logs'
                subprocess.run([
                    nssm_path, "set", service_name, "AppStdout", str(log_dir / f"{service_name}.log")
                ], check=True, capture_output=True, text=True)
                
                subprocess.run([
                    nssm_path, "set", service_name, "AppStderr", str(log_dir / f"{service_name}_error.log")
                ], check=True, capture_output=True, text=True)
                
                print(f"  ✓ Service '{service_name}' installed")
                self.services.append(service_name)
                installed_count += 1
                
            except subprocess.CalledProcessError as e:
                print(f"  ✗ Failed to install service '{service_name}': {e}")
                failed_count += 1
        
        print(f"\n  Summary: {installed_count} services installed, {failed_count} failed")
        return installed_count > 0
    
    def _get_nssm_path(self):
        """Get NSSM executable path (check if bundled or in PATH)"""
        # Check bundled NSSM
        bundled_nssm = Path(__file__).parent / 'nssm.exe'
        if bundled_nssm.exists():
            return str(bundled_nssm)
        
        # Check system PATH
        nssm_in_path = shutil.which('nssm')
        if nssm_in_path:
            return nssm_in_path
        
        return None
    
    def create_launcher_scripts(self):
        """Create convenient launcher scripts"""
        print("\nCreating launcher scripts...")
        
        # RUN_AGENT.bat (Main trading engine)
        run_bat = self.install_dir / 'RUN_AGENT.bat'
        with open(run_bat, 'w') as f:
            f.write('@echo off\n')
            f.write('echo Starting Main Trading Agent...\n')
            f.write(f'cd /d "{self.install_dir}\\TradingAgent"\n')
            f.write(f'"{sys.executable}" modules\\kotak_neo_auto_trader\\run_auto_trade.py\n')
            f.write('pause\n')
        print(f"  ✓ Created: {run_bat}")
        
        # START_ALL_SERVICES.bat
        start_all_bat = self.install_dir / 'START_ALL_SERVICES.bat'
        with open(start_all_bat, 'w') as f:
            f.write('@echo off\n')
            f.write('echo =====================================\n')
            f.write('echo Starting All Trading Agent Services\n')
            f.write('echo =====================================\n')
            f.write('echo.\n')
            for service in self.services:
                f.write(f'echo Starting {service}...\n')
                f.write(f'net start {service}\n')
                f.write('echo.\n')
            f.write('echo.\n')
            f.write('echo All services started!\n')
            f.write('pause\n')
        print(f"  ✓ Created: {start_all_bat}")
        
        # STOP_ALL_SERVICES.bat
        stop_all_bat = self.install_dir / 'STOP_ALL_SERVICES.bat'
        with open(stop_all_bat, 'w') as f:
            f.write('@echo off\n')
            f.write('echo =====================================\n')
            f.write('echo Stopping All Trading Agent Services\n')
            f.write('echo =====================================\n')
            f.write('echo.\n')
            for service in self.services:
                f.write(f'echo Stopping {service}...\n')
                f.write(f'net stop {service}\n')
                f.write('echo.\n')
            f.write('echo.\n')
            f.write('echo All services stopped!\n')
            f.write('pause\n')
        print(f"  ✓ Created: {stop_all_bat}")
        
        # Individual service scripts
        service_info = [
            ('ModularTradeAgent_Main', 'Main Auto Trader'),
            ('ModularTradeAgent_Monitor', 'Position Monitor'),
            ('ModularTradeAgent_EOD', 'EOD Cleanup'),
            ('ModularTradeAgent_Sell', 'Sell Orders'),
        ]
        
        for service_name, display_name in service_info:
            if service_name in self.services:
                # Start script
                start_bat = self.install_dir / f'START_{service_name.split("_")[-1].upper()}.bat'
                with open(start_bat, 'w') as f:
                    f.write('@echo off\n')
                    f.write(f'echo Starting {display_name}...\n')
                    f.write(f'net start {service_name}\n')
                    f.write('echo.\n')
                    f.write(f'echo {display_name} started!\n')
                    f.write('pause\n')
                
                # Stop script
                stop_bat = self.install_dir / f'STOP_{service_name.split("_")[-1].upper()}.bat'
                with open(stop_bat, 'w') as f:
                    f.write('@echo off\n')
                    f.write(f'echo Stopping {display_name}...\n')
                    f.write(f'net stop {service_name}\n')
                    f.write('echo.\n')
                    f.write(f'echo {display_name} stopped!\n')
                    f.write('pause\n')
        
        print(f"  ✓ Created individual service control scripts")
    
    def create_desktop_shortcut(self):
        """Create desktop shortcut"""
        try:
            import win32com.client
            shell = win32com.client.Dispatch("WScript.Shell")
            desktop = shell.SpecialFolders("Desktop")
            shortcut_path = os.path.join(desktop, "Trading Agent.lnk")
            shortcut = shell.CreateShortCut(shortcut_path)
            shortcut.Targetpath = str(self.install_dir / 'RUN_AGENT.bat')
            shortcut.WorkingDirectory = str(self.install_dir)
            shortcut.IconLocation = sys.executable
            shortcut.save()
            print(f"  ✓ Created desktop shortcut")
        except:
            print("  ! Could not create desktop shortcut (optional)")
    
    def run_installation(self):
        """Main installation workflow"""
        print("="*60)
        print("MODULAR TRADE AGENT - AUTOMATED INSTALLER")
        print("="*60)
        print(f"Installer Version: {format_version_info(self.installer_version)}")
        
        if self.installed_version:
            print(f"Installed Version: {format_version_info(self.installed_version)}")
            
            if self.installer_version == self.installed_version:
                print("Status: Reinstalling same version")
            elif self.installer_version > self.installed_version:
                print(f"Status: Upgrading from {self.installed_version} to {self.installer_version}")
            else:
                print(f"Status: Downgrading from {self.installed_version} to {self.installer_version}")
        else:
            print("Status: New installation")
        
        print()
        
        # Step 1: Check admin rights
        if not self.is_admin():
            print("Admin rights required for service installation.")
            print("Requesting elevation...")
            self.request_admin()
            return
        
        # Step 2: Create directories
        self.create_installation_directory()
        
        # Step 3: Extract application files
        if not self.extract_application_files():
            print("\nERROR: Failed to extract application files!")
            input("Press Enter to exit...")
            return
        
        # Step 4: Collect configuration
        if not self.collect_env_configuration():
            print("\nInstallation cancelled.")
            return
        
        # Step 4: Save configuration
        self.save_env_file()
        
        # Step 5: Install services
        services_installed = self.install_services()
        
        # Step 6: Create launcher scripts
        self.create_launcher_scripts()
        
        # Step 7: Create shortcut
        self.create_desktop_shortcut()
        
        # Step 8: Save version information
        print("\nSaving version information...")
        if save_version(self.installer_version, self.install_dir):
            print(f"  ✓ Saved version: {self.installer_version}")
        
        # Final summary
        print("\n" + "="*60)
        print("INSTALLATION COMPLETE!")
        print("="*60)
        print(f"\nInstallation directory: {self.install_dir}")
        print(f"Version: {format_version_info(self.installer_version)}")
        print(f"Configuration file: {self.install_dir / 'kotak_neo.env'}")
        print()
        
        if services_installed:
            print(f"Windows Services Installed: {len(self.services)}")
            for service in self.services:
                print(f"  - {service}")
            print()
            print("Service Control:")
            print("  - Start All: Run START_ALL_SERVICES.bat")
            print("  - Stop All: Run STOP_ALL_SERVICES.bat")
            print("  - Individual: START_MAIN.bat, START_MONITOR.bat, etc.")
            print()
        
        print("Quick Start:")
        print("  1. Double-click 'RUN_AGENT.bat' on desktop")
        print("  2. Or run START_SERVICE.bat to start as service")
        print()
        print("Happy Trading! 🚀")
        
        input("\nPress Enter to exit...")


if __name__ == "__main__":
    installer = TradeAgentInstaller()
    try:
        installer.run_installation()
    except KeyboardInterrupt:
        print("\n\nInstallation cancelled by user.")
        sys.exit(1)
    except Exception as e:
        print(f"\n\nERROR: Installation failed: {e}")
        import traceback
        traceback.print_exc()
        input("\nPress Enter to exit...")
        sys.exit(1)
