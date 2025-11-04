from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
import os
import subprocess
import glob
import threading
from pathlib import Path

from bs4 import BeautifulSoup

from utils.logger import logger

def _find_chromedriver():
    """Try to find ChromeDriver in common locations"""
    common_paths = [
        "/usr/bin/chromedriver",
        "/usr/local/bin/chromedriver",
        "/snap/bin/chromium.chromedriver",
        str(Path.home() / ".wdm" / "drivers" / "chromedriver" / "*" / "chromedriver*"),
    ]
    
    # Check system PATH
    result = subprocess.run(["which", "chromedriver"], capture_output=True, text=True)
    if result.returncode == 0 and result.stdout.strip():
        chromedriver_path = result.stdout.strip()
        if os.path.exists(chromedriver_path):
            return chromedriver_path
    
    # Check common paths
    for path in common_paths:
        if "*" in path:
            # Glob pattern
            matches = glob.glob(path)
            if matches:
                return matches[0]
        elif os.path.exists(path):
            return path
    
    return None

def _create_chrome_service(timeout=60):
    """Create Chrome service with timeout handling"""
    chromedriver_path = _find_chromedriver()
    
    if chromedriver_path:
        logger.info(f"Using system ChromeDriver at: {chromedriver_path}")
        return Service(chromedriver_path)
    else:
        logger.info("ChromeDriver not found in system, using webdriver-manager...")
        # Use threading timeout for cross-platform compatibility
        
        driver_path = [None]
        exception = [None]
        
        def install_driver():
            try:
                driver_path[0] = ChromeDriverManager().install()
            except Exception as e:
                exception[0] = e
        
        thread = threading.Thread(target=install_driver)
        thread.daemon = True
        thread.start()
        thread.join(timeout=timeout)
        
        if thread.is_alive():
            logger.warning(f"ChromeDriver installation timed out after {timeout} seconds")
            raise TimeoutError(f"ChromeDriver installation timed out after {timeout} seconds")
        
        if exception[0]:
            raise exception[0]
        
        if driver_path[0]:
            logger.info(f"ChromeDriver installed via webdriver-manager at: {driver_path[0]}")
            return Service(driver_path[0])
        else:
            raise RuntimeError("Failed to install ChromeDriver")

def get_stock_list():
    # Set Chrome options for headless mode and cross-platform compatibility
    chrome_options = Options()
    chrome_options.add_argument("--headless=new")  # Runs Chrome in headless mode
    chrome_options.add_argument("--disable-gpu")  # Disable GPU hardware acceleration
    chrome_options.add_argument("--no-sandbox")  # Needed for headless mode in Linux environments
    chrome_options.add_argument("--disable-dev-shm-usage")  # Overcome limited resource problems
    chrome_options.add_argument("--disable-software-rasterizer")  # Fix for snap Chromium

    # Set up Chrome driver with headless options
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)

    # URL of the chartink screener
    url = 'https://chartink.com/screener/daily-rsi-6602'

    try:
        # Open the page using Selenium
        driver.get(url)

        # Wait for the page to load completely
        WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.XPATH, '//span[text()="Copy"]')))

        # Find and click the "Run Scan" button
        run_scan_button = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, '//span[text()="Run Scan"]'))
        )
        run_scan_button.click()

        # Wait for scan results to load
        WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.XPATH, '//table[contains(@class, "rounded-b")]/tbody')))

        driver.execute_script("window.scrollBy(0, 800);")

        # Wait for table to be visible after scroll
        WebDriverWait(driver, 5).until(EC.visibility_of_element_located((By.XPATH, '//table[contains(@class, "rounded-b")]/tbody')))

        element = driver.find_element(By.XPATH, '//table[contains(@class, "rounded-b")]/tbody')

        # Get the HTML of that element
        html_content = element.get_attribute("outerHTML")

        soup = BeautifulSoup(html_content, 'html.parser')

        rows = soup.find_all('tr')

        stock_list = []

        for row in rows:
            cols = row.find_all('td')
            if len(cols) == 7:
                stock_name = cols[2].text.strip()
                logger.debug(f"Found stock: {stock_name}")
                stock_list.append(stock_name)

        copied_data = ', '.join(stock_list)

        # Log the copied data
        logger.info("Copied Data: %s", copied_data)

        return copied_data

    except Exception as e:
        logger.error(f"An error occurred: {e}")
        return None

    finally:
        # Close the browser window
        driver.quit()
