from selenium.common.exceptions import NoSuchElementException, TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import re

from urllib.parse import urlparse


class ElementNotFoundHandler:

    def __init__(self, driver, timeout=10):
        self.driver = driver
        self.timeout = timeout

    def generate_case_variations(self, text):
        if not text or not isinstance(text, str):
            return []

        variations = {text, text.lower(), text.upper(), text.capitalize()}

        if text == text.lower() and len(text) > 1:
            for i in range(3, min(7, len(text))):
                if len(text) > i:
                    first_part = text[:i]
                    second_part = text[i:]
                    variations.add(f"{first_part}{second_part.capitalize()}")

            common_prefixes = ['blue', 'red', 'green', 'user', 'admin', 'display', 'show', 'hide',
                               'input', 'output', 'form', 'data', 'get', 'set', 'main', 'sub']

            for prefix in common_prefixes:
                if text.startswith(prefix) and len(text) > len(prefix):
                    remaining = text[len(prefix):]
                    variations.add(f"{prefix}{remaining.capitalize()}")

        elif any(c.isupper() for c in text) and not text.isupper():
            lowercase = re.sub(r'([A-Z])', lambda x: x.group(1).lower(), text)
            variations.add(lowercase)

            snake_case = re.sub(r'([A-Z])', lambda x: '_' + x.group(1).lower(), text)
            if snake_case.startswith('_'):
                snake_case = snake_case[1:]
            variations.add(snake_case)

        return list(variations)

    def try_locators(self, locator_strategies, element_type="element"):
        for by_type, locator in locator_strategies:
            try:
                print(f"Trying {element_type} locator: {locator}")
                element = WebDriverWait(self.driver, self.timeout).until(
                    EC.presence_of_element_located((by_type, locator))
                )
                print(f"Found {element_type} with locator: {locator}")
                return element
            except (TimeoutException, NoSuchElementException):
                continue
        return None

    def try_clickable_locators(self, locator_strategies, element_type="element"):
        for by_type, locator in locator_strategies:
            try:
                print(f"Trying clickable {element_type} locator: {locator}")
                element = WebDriverWait(self.driver, self.timeout).until(
                    EC.element_to_be_clickable((by_type, locator))
                )
                print(f"Found clickable {element_type} with locator: {locator}")
                return element
            except (TimeoutException, NoSuchElementException):
                continue
        return None

    def extract_attribute_value(self, locator_value, attribute):
        if f"@{attribute}=" in locator_value:
            value = locator_value.split(f"@{attribute}=")[1].split("]")[0].strip("'\"")
            return value
        return None

    def extract_text_value(self, locator_value):
        if "text()=" in locator_value:
            value = locator_value.split("text()=")[1].strip("'\"[]")
            return value
        return None

    def get_domain_info(self):
        current_url = self.driver.current_url
        domain = ""
        main_domain = ""

        if current_url:
            try:
                parsed_url = urlparse(current_url)
                domain = f"{parsed_url.scheme}://{parsed_url.netloc}"

                domain_parts = parsed_url.netloc.split('.')
                if len(domain_parts) > 2:
                    main_domain_parts = domain_parts[-2:]
                    main_domain = f"{parsed_url.scheme}://{'.'.join(main_domain_parts)}"
                else:
                    main_domain = domain
            except Exception as e:
                print(f"Error extracting domain from current URL: {e}")

        return domain, main_domain

    def handle_link_not_found(self, original_locator, url):
        print(f"Link element not found with locator: {original_locator}. Attempting to navigate directly to: {url}")
        try:
            locator_type = original_locator.get("type")
            locator_value = original_locator.get("value")

            if locator_type == "xpath" and "//a" in locator_value:
                contains_strategies = []

                text_value = self.extract_text_value(locator_value)
                if text_value:
                    contains_strategies.append(
                        (By.XPATH, f"//a[contains(text(),'{text_value}')]")
                    )

                href_value = self.extract_attribute_value(locator_value, "href")
                if href_value:
                    contains_strategies.append(
                        (By.XPATH, f"//a[contains(@href,'{href_value}')]")
                    )
                    if "/" in href_value:
                        path_part = href_value.split("/")[-1]
                        if path_part:
                            contains_strategies.append(
                                (By.XPATH, f"//a[contains(@href,'{path_part}')]")
                            )

                element = self.try_clickable_locators(contains_strategies, "link")
                if element:
                    element.click()
                    return []

            domain, main_domain = self.get_domain_info()
            urls_to_try = []

            if url.startswith('/'):
                if domain:
                    urls_to_try.append(f"{domain}{url}")
                if main_domain and main_domain != domain:
                    urls_to_try.append(f"{main_domain}{url}")
                urls_to_try.append(f"https:{url}" if url.startswith('//') else f"https://{url.lstrip('/')}")
            elif not url.startswith(('http://', 'https://')):
                if domain:
                    domain_netloc = domain.split('://')[1]
                    if domain_netloc not in url:
                        urls_to_try.append(f"{domain}/{url.lstrip('/')}")

                if main_domain and main_domain != domain:
                    main_domain_netloc = main_domain.split('://')[1]
                    if main_domain_netloc not in url:
                        urls_to_try.append(f"{main_domain}/{url.lstrip('/')}")

                urls_to_try.append(f"https://{url}")
            else:
                urls_to_try.append(url)

            if not urls_to_try:
                urls_to_try.append(url)

            return urls_to_try
        except Exception as e:
            print(f"Failed to process URL {url}: {e}")
            return [url]

    def handle_button_not_found(self, original_locator):
        locator_type = original_locator.get("type")
        locator_value = original_locator.get("value")

        print(f"Button not found with locator: {original_locator}. Trying alternatives...")

        if locator_type != "xpath" or "//button" not in locator_value:
            return None

        contains_strategies = []

        text_value = self.extract_text_value(locator_value)
        if text_value:
            contains_strategies.append(
                (By.XPATH, f"//button[contains(text(),'{text_value}')]")
            )
            contains_strategies.append(
                (By.XPATH, f"//button//*[contains(text(),'{text_value}')]")
            )

        testid = self.extract_attribute_value(locator_value, "data-testid")
        if testid:
            contains_strategies.append(
                (By.XPATH, f"//button[contains(@data-testid,'{testid}')]")
            )

        class_value = self.extract_attribute_value(locator_value, "class")
        if class_value:
            contains_strategies.append(
                (By.XPATH, f"//button[contains(@class,'{class_value}')]")
            )

        element = self.try_clickable_locators(contains_strategies, "button")
        if element:
            return element

        fallback_strategies = []

        fallback_strategies.append(
            (By.XPATH, locator_value.replace("//button", "//a"))
        )

        if text_value:
            fallback_strategies.append(
                (By.XPATH, f"//div[contains(text(),'{text_value}')]")
            )
            fallback_strategies.append(
                (By.XPATH, f"//span[contains(text(),'{text_value}')]")
            )

        if testid:
            fallback_strategies.append(
                (By.XPATH, f"//*[@data-testid='{testid}']")
            )

        return self.try_clickable_locators(fallback_strategies, "button fallback")

    def handle_input_not_found(self, original_locator):
        locator_type = original_locator.get("type")
        locator_value = original_locator.get("value")

        print(f"Input not found with locator: {original_locator}. Trying alternatives...")

        if locator_type != "xpath" or "//input" not in locator_value:
            return None

        contains_strategies = []

        name_value = self.extract_attribute_value(locator_value, "name")
        if name_value:
            contains_strategies.append(
                (By.XPATH, f"//input[contains(@name,'{name_value}')]")
            )

            for variation in self.generate_case_variations(name_value):
                if variation != name_value:
                    contains_strategies.append(
                        (By.XPATH, f"//input[@name='{variation}']")
                    )
                    contains_strategies.append(
                        (By.XPATH, f"//input[contains(@name,'{variation}')]")
                    )

        id_value = self.extract_attribute_value(locator_value, "id")
        if id_value:
            contains_strategies.append(
                (By.XPATH, f"//input[contains(@id,'{id_value}')]")
            )
            contains_strategies.append(
                (By.XPATH, f"//input[@name='{id_value}']")
            )
            contains_strategies.append(
                (By.XPATH, f"//input[contains(@name,'{id_value}')]")
            )

            for variation in self.generate_case_variations(id_value):
                if variation != id_value:  # Skip the original as it's already included
                    contains_strategies.append(
                        (By.XPATH, f"//input[@id='{variation}']")
                    )
                    contains_strategies.append(
                        (By.XPATH, f"//input[contains(@id,'{variation}')]")
                    )
                    contains_strategies.append(
                        (By.XPATH, f"//input[@name='{variation}']")
                    )
                    contains_strategies.append(
                        (By.XPATH, f"//input[contains(@name,'{variation}')]")
                    )

        placeholder_value = self.extract_attribute_value(locator_value, "placeholder")
        if placeholder_value:
            contains_strategies.append(
                (By.XPATH, f"//input[contains(@placeholder,'{placeholder_value}')]")
            )

        element = self.try_locators(contains_strategies, "input")
        if element:
            return element

        fallback_strategies = []

        if name_value:
            fallback_strategies.append(
                (By.XPATH, f"//input[@name='{name_value.lower()}']")
            )
            fallback_strategies.append(
                (By.XPATH, f"//input[@name='{name_value.upper()}']")
            )
            fallback_strategies.append(
                (By.XPATH, f"//input[@name='{name_value.capitalize()}']")
            )
            fallback_strategies.append(
                (By.XPATH, f"//input[@id='{name_value}']")
            )

        fallback_strategies.append(
            (By.XPATH, locator_value.replace("//input", "//textarea"))
        )

        return self.try_locators(fallback_strategies, "input fallback")

    def handle_select_not_found(self, original_locator, input_value=None):
        locator_type = original_locator.get("type")
        locator_value = original_locator.get("value")

        print(f"Select element not found with locator: {original_locator}. Trying alternatives...")

        if locator_type != "xpath" or "//select" not in locator_value:
            return None

        contains_strategies = []

        name_value = self.extract_attribute_value(locator_value, "name")
        if name_value:
            contains_strategies.append(
                (By.XPATH, f"//select[contains(@name,'{name_value}')]")
            )

            for variation in self.generate_case_variations(name_value):
                if variation != name_value:
                    contains_strategies.append(
                        (By.XPATH, f"//select[@name='{variation}']")
                    )
                    contains_strategies.append(
                        (By.XPATH, f"//select[contains(@name,'{variation}')]")
                    )

        id_value = self.extract_attribute_value(locator_value, "id")
        if id_value:
            contains_strategies.append(
                (By.XPATH, f"//select[contains(@id,'{id_value}')]")
            )

            for variation in self.generate_case_variations(id_value):
                if variation != id_value:
                    contains_strategies.append(
                        (By.XPATH, f"//select[@id='{variation}']")
                    )
                    contains_strategies.append(
                        (By.XPATH, f"//select[contains(@id,'{variation}')]")
                    )

            if input_value and isinstance(input_value, str) and input_value.strip():
                contains_strategies.append(
                    (By.XPATH, f"//input[@type='radio' and @name='{id_value}' and @value='{input_value}']")
                )
                contains_strategies.append(
                    (By.XPATH, f"//input[@type='radio' and @name='{id_value}' and @value='{input_value.lower()}']")
                )
            else:
                contains_strategies.append(
                    (By.XPATH, f"//input[@type='radio' and @name='{id_value}']")
                )

        class_value = self.extract_attribute_value(locator_value, "class")
        if class_value:
            contains_strategies.append(
                (By.XPATH, f"//select[contains(@class,'{class_value}')]")
            )

        element = self.try_locators(contains_strategies, "select")
        if element:
            return element

        fallback_strategies = []

        if name_value:
            fallback_strategies.append(
                (By.XPATH, f"//div[@data-select='{name_value}']")
            )
            fallback_strategies.append(
                (By.XPATH, f"//div[contains(@class, 'select') and @id='{name_value}']")
            )
            fallback_strategies.append(
                (By.XPATH, f"//input[@type='select' and @name='{name_value}']")
            )

        return self.try_locators(fallback_strategies, "select fallback")
