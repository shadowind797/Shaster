import json
import os
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException


def run_tests_from_file(file_path, browser='chrome', headless=False):
    try:
        with open(file_path, 'r') as file:
            test_data = json.load(file)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"Error loading test file: {e}")
        return {"error": str(e)}

    driver = setup_webdriver(browser, headless)
    test_results = {}

    try:
        for test in test_data:
            test_name = test.get("testName", "Unnamed Test")
            print(f"Running test: {test_name}")

            try:
                for step in test.get("steps", []):
                    process_test_step(driver, step)

                test_results[test_name] = "PASS"
                print(f"Test '{test_name}' passed")

            except Exception as e:
                test_results[test_name] = f"FAIL: {str(e)}"
                print(f"Test '{test_name}' failed: {e}")
                driver.save_screenshot(f"{test_name.replace(' ', '_')}_failure.png")

    finally:
        driver.quit()

    return test_results


def setup_webdriver(browser='chrome', headless=False):
    if browser.lower() == 'chrome':
        options = webdriver.ChromeOptions()
        if headless:
            options.add_argument('--headless')
        return webdriver.Chrome(options=options)

    elif browser.lower() == 'firefox':
        options = webdriver.FirefoxOptions()
        if headless:
            options.add_argument('--headless')
        return webdriver.Firefox(options=options)

    elif browser.lower() == 'edge':
        options = webdriver.EdgeOptions()
        if headless:
            options.add_argument('--headless')
        return webdriver.Edge(options=options)

    else:
        raise ValueError(f"Unsupported browser: {browser}")


def process_test_step(driver, step):
    action = step.get("action")
    locator = step.get("locator", {})
    locator_type = locator.get("type")
    locator_value = locator.get("value")

    by_type = get_by_type(locator_type)

    timeout = 10

    if action == "goto":
        url = locator_value
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url
        driver.get(url)

    elif action == "input":
        input_value = step.get("input_value", "")
        element = find_element(driver, by_type, locator_value)
        element.clear()
        element.send_keys(input_value)

    elif action == "click":
        element = find_element(driver, by_type, locator_value)
        element.click()

    elif action == "waitForElementVisible":
        try:
            WebDriverWait(driver, timeout).until(
                EC.visibility_of_element_located((by_type, locator_value))
            )
        except TimeoutException:
            raise TimeoutException(f"Element {locator_value} not visible after {timeout} seconds")

    elif action == "waitForRedirect":
        expected_url = locator_value
        try:
            WebDriverWait(driver, timeout).until(
                lambda d: d.current_url == expected_url
            )
        except TimeoutException:
            raise TimeoutException(
                f"URL did not redirect to {expected_url} after {timeout} seconds. Current URL: {driver.current_url}")

    else:
        raise ValueError(f"Unsupported action: {action}")


def get_by_type(locator_type):
    locator_map = {
        "id": By.ID,
        "name": By.NAME,
        "xpath": By.XPATH,
        "css": By.CSS_SELECTOR,
        "class": By.CLASS_NAME,
        "link_text": By.LINK_TEXT,
        "partial_link_text": By.PARTIAL_LINK_TEXT,
        "tag": By.TAG_NAME
    }

    if locator_type in locator_map:
        return locator_map[locator_type]
    else:
        return By.XPATH


def find_element(driver, by_type, locator_value):
    try:
        element = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((by_type, locator_value))
        )
        return element
    except TimeoutException:
        raise NoSuchElementException(f"Element not found: {locator_value}")


def run_test(test_name):
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    file_path = os.path.join(project_root, "data", "autos", test_name)

    if not os.path.exists(file_path):
        print(f"File not found: {file_path}")
        return

    results = run_tests_from_file(file_path)
    print("\nTest Results Summary:")
    for test_name, result in results.items():
        print(f"{test_name}: {result}")
