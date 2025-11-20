from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
import os
import platform
import subprocess
import tempfile
import shutil

from bs4 import BeautifulSoup

from utils.logger import logger


def _find_chrome_binary():
    """Find Chrome/Chromium binary path based on the system."""
    # Common Chrome/Chromium binary paths
    possible_paths = [
        "/usr/bin/google-chrome",
        "/usr/bin/google-chrome-stable",
        "/usr/bin/chromium-browser",
        "/usr/bin/chromium",
        "/snap/bin/chromium",
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",  # macOS
        "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",  # Windows
        "C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe",  # Windows
    ]

    # Check if CHROME_BIN environment variable is set
    if os.environ.get("CHROME_BIN"):
        chrome_bin = os.environ.get("CHROME_BIN")
        if os.path.exists(chrome_bin):
            return chrome_bin

    # Try to find Chrome/Chromium using which command
    try:
        if platform.system() != "Windows":
            result = subprocess.run(
                ["which", "chromium-browser"], capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0 and result.stdout.strip():
                return result.stdout.strip()

            result = subprocess.run(
                ["which", "chromium"], capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0 and result.stdout.strip():
                return result.stdout.strip()

            result = subprocess.run(
                ["which", "google-chrome"], capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0 and result.stdout.strip():
                return result.stdout.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass

    # Check common paths
    for path in possible_paths:
        if os.path.exists(path):
            return path

    return None


def _find_chromedriver():
    """Find ChromeDriver binary path."""
    possible_paths = [
        "/usr/bin/chromedriver",
        "/usr/local/bin/chromedriver",
        "/snap/bin/chromedriver",
    ]

    # Check if CHROMEDRIVER_PATH environment variable is set
    if os.environ.get("CHROMEDRIVER_PATH"):
        chromedriver_path = os.environ.get("CHROMEDRIVER_PATH")
        if os.path.exists(chromedriver_path):
            return chromedriver_path

    # Try to find using which command
    try:
        if platform.system() != "Windows":
            result = subprocess.run(
                ["which", "chromedriver"], capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0 and result.stdout.strip():
                return result.stdout.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass

    # Check common paths
    for path in possible_paths:
        if os.path.exists(path):
            return path

    return None


def _create_minimal_chrome_options(chrome_binary, user_data_dir):
    """Create minimal Chrome options for maximum compatibility."""
    options = Options()
    options.binary_location = chrome_binary
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--remote-debugging-port=0")  # Let Chrome choose port
    if user_data_dir:
        options.add_argument(f"--user-data-dir={user_data_dir}")
    return options


def _create_basic_chrome_options(chrome_binary, user_data_dir):
    """Create basic Chrome options."""
    options = Options()
    options.binary_location = chrome_binary
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--disable-extensions")
    options.add_argument("--disable-logging")
    options.add_argument("--log-level=3")
    options.add_argument("--remote-debugging-port=0")
    if user_data_dir:
        options.add_argument(f"--user-data-dir={user_data_dir}")
    return options


def _create_no_profile_chrome_options(chrome_binary):
    """Create Chrome options without user data dir (for testing)."""
    options = Options()
    options.binary_location = chrome_binary
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--remote-debugging-port=0")
    # Don't set user-data-dir - let Chrome use temp
    return options


def get_stock_list():
    driver = None  # Initialize to avoid NameError in finally block
    temp_user_data_dir = None  # Initialize for cleanup in finally block

    try:
        # Find and set Chrome binary path first
        chrome_binary = _find_chrome_binary()
        if not chrome_binary:
            logger.error(
                "Chrome/Chromium binary not found. Please install Chromium: sudo apt-get install chromium-browser"
            )
            return None

        logger.debug(f"Using Chrome binary: {chrome_binary}")

        # Test Chromium directly first (silent - only log if there's an issue)
        try:
            logger.debug("Testing Chromium headless mode...")
            test_result = subprocess.run(
                [
                    chrome_binary,
                    "--headless",
                    "--disable-gpu",
                    "--no-sandbox",
                    "--dump-dom",
                    "data:text/html,<html><body>Test</body></html>",
                ],
                capture_output=True,
                timeout=10,
            )
            if test_result.returncode != 0:
                logger.debug(f"Chromium direct test failed with exit code {test_result.returncode}")
                logger.debug(
                    f"Error output: {test_result.stderr.decode('utf-8', errors='ignore')[:500]}"
                )
        except Exception as e:
            logger.debug(f"Could not test Chromium directly: {e}")

        # Create a user data directory - try /tmp first (more reliable on Linux)
        import time

        temp_user_data_dir = None

        # Try multiple locations for user data directory
        possible_locations = [
            f"/tmp/chrome_user_data_{os.getpid()}_{int(time.time())}",  # Use /tmp with PID
            os.path.join(
                os.path.expanduser("~"), f".chrome_user_data_{int(time.time())}"
            ),  # Home directory
            f"/tmp/chrome_user_data_{int(time.time())}",  # Simple /tmp
        ]

        for location in possible_locations:
            try:
                os.makedirs(location, mode=0o700, exist_ok=True)
                # Test write permissions
                test_file = os.path.join(location, ".test_write")
                with open(test_file, "w") as f:
                    f.write("test")
                os.remove(test_file)
                temp_user_data_dir = location
                logger.debug(f"Using Chrome user data directory: {temp_user_data_dir}")
                break
            except Exception as e:
                logger.debug(f"Could not use {location}: {e}")
                continue

        if not temp_user_data_dir:
            logger.warning(
                "Could not create user data directory in any location. Chrome may use default."
            )

        # Try ChromeDriver initialization - use the known working strategy first
        driver = None
        chromedriver_path = _find_chromedriver()

        # Primary strategy: System ChromeDriver without user data dir (known to work)
        if chromedriver_path:
            try:
                logger.debug(
                    "Initializing Chrome WebDriver with system ChromeDriver (no user data dir)..."
                )
                chrome_options = _create_no_profile_chrome_options(chrome_binary)
                service = Service(chromedriver_path)
                driver = webdriver.Chrome(service=service, options=chrome_options)

                # Test if driver is working
                driver.set_page_load_timeout(10)
                driver.get("data:text/html,<html><body>Test</body></html>")
                logger.info(
                    f"[OK] Chrome WebDriver initialized successfully using: System ChromeDriver without user data dir"
                )
            except Exception as e:
                logger.debug(f"Primary strategy failed: {e}")
                if driver:
                    try:
                        driver.quit()
                    except:
                        pass
                    driver = None

        # Fallback strategies if primary fails
        if driver is None:
            logger.debug("Primary strategy failed, trying fallback strategies...")
            strategies = [
                # Fallback 1: ChromeDriverManager without user data dir
                {
                    "name": "ChromeDriverManager without user data dir",
                    "options": lambda: _create_no_profile_chrome_options(chrome_binary),
                    "service": lambda: Service(ChromeDriverManager().install()),
                },
                # Fallback 2: System ChromeDriver with minimal options
                {
                    "name": "System ChromeDriver with minimal options",
                    "options": lambda: _create_minimal_chrome_options(
                        chrome_binary, temp_user_data_dir
                    ),
                    "service": lambda: (
                        Service(chromedriver_path)
                        if chromedriver_path
                        else Service(ChromeDriverManager().install())
                    ),
                },
                # Fallback 3: ChromeDriverManager with minimal options
                {
                    "name": "ChromeDriverManager with minimal options",
                    "options": lambda: _create_minimal_chrome_options(
                        chrome_binary, temp_user_data_dir
                    ),
                    "service": lambda: Service(ChromeDriverManager().install()),
                },
            ]

            for strategy in strategies:
                try:
                    logger.debug(f"Trying fallback strategy: {strategy['name']}")
                    chrome_options = strategy["options"]()
                    service = strategy["service"]()

                    # Create driver with explicit service
                    logger.debug(
                        f"Creating Chrome driver with service: {service.path if hasattr(service, 'path') else 'ChromeDriverManager'}"
                    )
                    driver = webdriver.Chrome(service=service, options=chrome_options)

                    # Test if driver is actually working - use a simple test
                    try:
                        driver.set_page_load_timeout(10)
                        driver.get("data:text/html,<html><body>Test</body></html>")
                        page_title = driver.title
                        logger.info(
                            f"[OK] Chrome WebDriver initialized successfully using: {strategy['name']}"
                        )
                        break
                    except Exception as test_error:
                        logger.debug(f"Driver created but test failed: {test_error}")
                        driver.quit()
                        driver = None
                        raise

                except Exception as e:
                    error_msg = str(e)
                    # Only log detailed errors at debug level to reduce noise
                    logger.debug(
                        f"Fallback strategy '{strategy['name']}' failed: {error_msg[:200]}"
                    )
                    if driver:
                        try:
                            driver.quit()
                        except:
                            pass
                        driver = None
                    continue

        if driver is None:
            raise Exception(
                "All ChromeDriver initialization strategies failed. Please check Chromium installation and system dependencies."
            )

        # URL of the chartink screener
        url = "https://chartink.com/screener/daily-rsi-6602"

        # Open the page using Selenium
        driver.get(url)

        # Wait for the page to load completely
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.XPATH, '//span[text()="Copy"]'))
        )

        # Find and click the "Run Scan" button
        run_scan_button = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, '//span[text()="Run Scan"]'))
        )
        run_scan_button.click()

        # Wait for scan results to load
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located(
                (By.XPATH, '//table[contains(@class, "rounded-b")]/tbody')
            )
        )

        driver.execute_script("window.scrollBy(0, 800);")

        # Wait for table to be visible after scroll
        WebDriverWait(driver, 5).until(
            EC.visibility_of_element_located(
                (By.XPATH, '//table[contains(@class, "rounded-b")]/tbody')
            )
        )

        element = driver.find_element(By.XPATH, '//table[contains(@class, "rounded-b")]/tbody')

        # Get the HTML of that element
        html_content = element.get_attribute("outerHTML")

        soup = BeautifulSoup(html_content, "html.parser")

        rows = soup.find_all("tr")
        stock_list = []
        for row in rows:
            cols = row.find_all("td")
            if len(cols) == 7:
                stock_name = cols[2].text.strip()
                logger.debug(f"Found stock: {stock_name}")
                stock_list.append(stock_name)

        copied_data = ", ".join(stock_list)

        # Log the copied data
        logger.info("Copied Data: %s", copied_data)
        return copied_data

    except Exception as e:
        logger.error(f"An error occurred: {e}")
        return None

    finally:
        # Close the browser window if it was created
        if driver is not None:
            try:
                driver.quit()
            except Exception as e:
                logger.warning(f"Error closing driver: {e}")

        # Clean up temporary user data directory
        try:
            if temp_user_data_dir and os.path.exists(temp_user_data_dir):
                shutil.rmtree(temp_user_data_dir, ignore_errors=True)
                logger.debug(
                    f"Cleaned up temporary Chrome user data directory: {temp_user_data_dir}"
                )
        except Exception as e:
            logger.debug(f"Error cleaning up temporary directory: {e}")
