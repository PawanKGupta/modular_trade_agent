from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import pyperclip
import time

from utils.logger import logger


def get_stock_list():
    # Set Chrome options for headless mode
    chrome_options = Options()
    # chrome_options.add_argument("--headless")  # Runs Chrome in headless mode
    chrome_options.add_argument("--disable-gpu")  # Disable GPU hardware acceleration (optional)
    chrome_options.add_argument("--no-sandbox")  # Needed for headless mode in some environments (like Linux)

    # Set up Chrome driver with headless options
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)

    # URL of the chartink screener
    url = 'https://chartink.com/screener/daily-rsi-6602'

    # Open the page using Selenium
    driver.get(url)
    driver.maximize_window()

    # Take a screenshot after page load to check if the page is fully loaded
    # driver.save_screenshot("after_page_load.png")

    # Wait for the page to load completely (replace time.sleep() with WebDriverWait)
    WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.XPATH, '//span[text()="Copy"]')))

    # Try to find the "Copy" button and click it
    try:
        run_scan_button = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, '//span[text()="Run Scan"]'))
        )
        # Take a screenshot before clicking the "Copy" button to see the button's state
        # driver.save_screenshot("before_copy_button_click.png")
        run_scan_button.click()
        time.sleep(5)

        driver.execute_script("window.scrollBy(0, 800);")
        # Wait for the copy button to be clickable
        copy_button = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, '//span[text()="Copy"]'))
        )
        # Take a screenshot before clicking the "Copy" button to see the button's state
        # driver.save_screenshot("before_copy_button_click.png")
        copy_button.click()

        # Wait for the "Symbols" button to be clickable and click it
        symbols_button = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, '//span[text()="symbols"]'))
        )
        # Take a screenshot before clicking the "Symbols" button
        # driver.save_screenshot("before_symbols_button_click.png")
        symbols_button.click()

        # Wait to ensure the clipboard is populated (you can increase the sleep time here)
        time.sleep(3)  # Increased wait time to make sure the clipboard has time to copy

        # Get the copied data from the clipboard
        copied_data = pyperclip.paste()

        # Print the copied data to the console
        logger.info("Copied Data: %s", copied_data)
        return copied_data

    except Exception as e:
        logger.error(f"An error occurred: {e}")

    finally:
        # Close the browser window
        driver.quit()
