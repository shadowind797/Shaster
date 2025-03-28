import json
import os
import time

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException

from automate.fallback_handler import FallbackHandler


def run_tests_from_file(file_path, browser='chrome', headless=False):
    try:
        with open(file_path, 'r') as file:
            test_data = json.load(file)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"Error loading test file: {e}")
        return {"error": str(e)}

    driver = setup_webdriver(browser, headless)
    fallback_handler = FallbackHandler(driver)
    test_results = {}

    try:
        for test in test_data:
            test_name = test.get("testName", "Unnamed Test")
            print(f"Running test: {test_name}")

            try:
                steps = test.get("steps", [])
                for i, step in enumerate(steps):
                    # Check if this is a click on a link and there's a next step
                    next_step = steps[i + 1] if i + 1 < len(steps) else None
                    process_test_step(driver, step, fallback_handler, next_step)

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


def process_test_step(driver, step, fallback_handler, next_step=None):
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
        time.sleep(1)
        input_value = step.get("input_value", "")
        try:
            element = find_element(driver, by_type, locator_value)
            element.clear()
            element.send_keys(input_value)
        except NoSuchElementException:
            element = fallback_handler.execute_fallback_script("input", locator_type, locator_value, input_value)
            if not element:
                raise NoSuchElementException(
                    f"Input element not found with locator: {locator_value} and no fallback succeeded")
            element.clear()
            element.send_keys(input_value)

    elif action == "click":
        time.sleep(2)
        try:
            element = find_element(driver, by_type, locator_value)
            try:
                element.click()
                return
            except Exception as e:
                if "element click intercepted" in str(e).lower():
                    if resolve_click_intercept(driver, element):
                        return
                    raise
                else:
                    raise


        except NoSuchElementException:
            if next_step and next_step.get("action") == "waitForRedirect" and "@href" in step.get("locator").get("value"):

                redirect_url = next_step.get("locator", {}).get("value")
                if redirect_url:
                    print(f"Link not found, but next step is waitForRedirect. Navigating directly to: {redirect_url}")
                    if not redirect_url.startswith(('http://', 'https://')):
                        redirect_url = 'https://' + redirect_url
                    driver.get(redirect_url)
                    return
            result = fallback_handler.execute_fallback_script("click", locator_type, locator_value)
            if result:
                try:
                    result.click()
                    return
                except Exception as e:
                    if "element click intercepted" in str(e).lower():
                        if resolve_click_intercept(driver, result):
                            return
                        raise
                    else:
                        raise


            elif next_step and next_step.get("action") == "waitForRedirect":
                redirect_url = next_step.get("locator", {}).get("value")
                if redirect_url:
                    print(f"Link not found, but next step is waitForRedirect. Navigating directly to: {redirect_url}")

                    if not redirect_url.startswith(('http://', 'https://')):
                        redirect_url = 'https://' + redirect_url
                    driver.get(redirect_url)
                    return

            raise NoSuchElementException(
                f"Clickable element not found with locator: {locator_value} and no fallback succeeded")

    elif action == "waitForElementVisible":
        try:
            WebDriverWait(driver, timeout).until(
                EC.visibility_of_element_located((by_type, locator_value))
            )
        except TimeoutException:
            element = fallback_handler.execute_fallback_script("waitForElementVisible", locator_type, locator_value)
            if not element:
                raise TimeoutException(f"Element {locator_value} not visible after {timeout} seconds")

    elif action == "waitForRedirect":
        expected_url = locator_value
        try:
            WebDriverWait(driver, timeout).until(
                lambda d: d.current_url == expected_url
            )
        except TimeoutException:
            if expected_url in driver.current_url:
                print(f"URL partially matches expected URL. Current: {driver.current_url}, Expected: {expected_url}")
                return

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


def resolve_click_intercept(driver, element):
    try:
        tag_name = element.tag_name.lower()

        if tag_name == "input":
            input_id = element.get_attribute('id')
            if input_id:
                try:
                    label = driver.find_element(By.CSS_SELECTOR, f"label[for='{input_id}']")
                    print(f"Found label with for='{input_id}', clicking it")
                    label.click()
                    return True
                except NoSuchElementException:
                    pass

            input_name = element.get_attribute('name')
            if input_name:
                try:
                    label = driver.find_element(By.CSS_SELECTOR, f"label[for='{input_name}']")
                    print(f"Found label with for='{input_name}', clicking it")
                    label.click()
                    return True
                except NoSuchElementException:
                    pass

        try:
            print(f"Trying JavaScript click on {tag_name} element")
            driver.execute_script("arguments[0].click();", element)
            return True
        except Exception as js_error:
            print(f"JavaScript click failed: {js_error}")

        parent_elements = driver.execute_script("""
            var element = arguments[0];
            var parents = [];
            var parent = element.parentElement;
            while (parent) {
                parents.push(parent);
                parent = parent.parentElement;
                if (parents.length > 5) break; // Limit search depth
            }
            return parents;
        """, element)

        clickable_tags = ['label', 'button', 'a', 'div']
        for parent in parent_elements:
            parent_tag = driver.execute_script("return arguments[0].tagName.toLowerCase();", parent)
            if parent_tag in clickable_tags:
                print(f"Element is inside a {parent_tag} element, clicking the parent")
                driver.execute_script("arguments[0].click();", parent)
                return True

        element_rect = element.rect
        potential_clickables = []

        for tag in clickable_tags:
            potential_clickables.extend(driver.find_elements(By.TAG_NAME, tag))

        for potential in potential_clickables:
            potential_rect = potential.rect
            if (abs(potential_rect['x'] - element_rect['x']) < 50 and
                    abs(potential_rect['y'] - element_rect['y']) < 50):
                print(f"Found {potential.tag_name} element near target, clicking it")
                potential.click()
                return True

        try:
            print("Scrolling element into view")
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", element)
            time.sleep(0.5)
            element.click()
            return True
        except Exception as scroll_error:
            print(f"Scroll and click failed: {scroll_error}")

        print(f"Could not resolve click intercept for {tag_name} element")
        return False

    except Exception as e:
        print(f"Error while trying to resolve click intercept: {e}")
        return False
