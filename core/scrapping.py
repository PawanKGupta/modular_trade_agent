from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time

from bs4 import BeautifulSoup

from utils.logger import logger

def get_stock_list():
    driver = None  # Initialize to avoid NameError in finally block
    
    try:
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
        # Close the browser window if it was created
        if driver is not None:
            try:
                driver.quit()
            except Exception as e:
                logger.warning(f"Error closing driver: {e}")