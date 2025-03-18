import traceback
import re
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException

from urllib.parse import urlparse


class FallbackHandler:

    def __init__(self, driver, timeout=0.5, fallback_delay=0.5):
        self.driver = driver
        self.timeout = timeout
        self.fallback_delay = fallback_delay
        self.strategy_cache = {}

    def execute_fallback_script(self, current_action, locator_type, locator_value, input_value=None):
        print(f"Executing fallback for action: {current_action}, locator: {locator_type}={locator_value}")

        try:
            locator = {"type": locator_type, "value": locator_value}

            if current_action == "click":
                return self._handle_click_fallback(locator)

            elif current_action == "input":
                return self._handle_input_fallback(locator, input_value)

            elif current_action == "select":
                return self._handle_select_fallback(locator, input_value)

            elif current_action == "waitForElementVisible":
                return self._handle_wait_visible_fallback(locator)

            return None
        except Exception as e:
            print(f"Error in fallback handler for {current_action}: {str(e)}")
            print(traceback.format_exc())
            return None

    def _handle_click_fallback(self, locator):
        locator_type = locator.get("type")
        locator_value = locator.get("value")

        cache_key = f"click_{locator_type}_{locator_value}"
        cached_element = self._try_cached_strategy(cache_key, EC.element_to_be_clickable)
        if cached_element:
            return cached_element

        fallback_strategies = []
        html_tagname = self._extract_tag_name(locator_value)

        self._add_contains_strategy(fallback_strategies, locator_value)

        if "//label" in locator_value:
            self._check_separate_words(locator_type, locator_value, fallback_strategies)

        if "text()" in locator_value:
            text = self._extract_text_value(locator_value)

            if "//label" in locator_value:
                if text:
                    sanitized_text = self._sanitize_xpath_value(text)
                    fallback_strategies.append((By.XPATH, f"//input[@value={sanitized_text}]"))
                    fallback_strategies.append((By.XPATH, f"//input[contains(@value, {sanitized_text})]"))

            if text:
                case_variations = self._generate_case_variations(text)
                if html_tagname == "button":
                    for variation in case_variations:
                        fallback_strategies.append((By.XPATH, f"//{html_tagname}/span[text()='{variation}']"))
                        fallback_strategies.append((By.XPATH, f"//{html_tagname}/span[contains(text(), '{variation}')]"))
                elif html_tagname == "div":
                    self._check_separate_words(locator_type, f"//p/span[contains(text(), '{text}')]", fallback_strategies)
                    self._check_separate_words(locator_type, f"//{html_tagname}/span[contains(text(), '{text}')]", fallback_strategies)
                else:
                    for variation in case_variations:
                        fallback_strategies.append((By.XPATH, f"//{html_tagname}[text()='{variation}']"))
                        fallback_strategies.append((By.XPATH, f"//{html_tagname}[contains(text(), '{variation}')]"))

            fallback_strategies.append((By.XPATH, locator_value.replace("//button", "//button/span")))
            fallback_strategies.append((By.XPATH, locator_value.replace("//button", "//button/a")))
            fallback_strategies.append((By.XPATH, locator_value.replace("//a", "//button/span")))
            fallback_strategies.append((By.XPATH, locator_value.replace("//a", "//button/a")))

        if locator_type in ["id", "name"] or "@name" in locator_value or "@id" in locator_value:
            fallback_strategies += self._check_id_name(locator_type, locator_value, "*", "")

        if not "//label" in locator_value:
            self._check_separate_words(locator_type, locator_value, fallback_strategies)

        if locator_type == "xpath" and "//button" in locator_value:
            fallback_strategies.append((By.XPATH, locator_value.replace("//button", "//a")))
            fallback_strategies.append((By.XPATH, locator_value.replace("//button", "//div[contains(@class, 'btn')]")))
            fallback_strategies.append((By.XPATH, locator_value.replace("//button", "//span[contains(@class, 'btn')]")))

        element = self._try_clickable_locators(fallback_strategies)

        self._cache_successful_strategy(element, fallback_strategies, cache_key)

        return element

    def _handle_input_fallback(self, locator, input_value):
        locator_type = locator.get("type")
        locator_value = locator.get("value")

        cache_key = f"input_{locator_type}_{locator_value}"
        cached_element = self._try_cached_strategy(cache_key, EC.presence_of_element_located)
        if cached_element:
            return cached_element

        fallback_strategies = []

        if locator_type == "xpath" and "//input" in locator_value:
            self._add_contains_strategy(fallback_strategies, locator_value)

        if locator_type in ["id", "name"] or "name" in locator_value or "id" in locator_value:
            fallback_strategies += self._check_id_name(locator_type, locator_value, "input", "textarea")

        fallback_strategies.append((By.XPATH, locator_value.replace("//input", "//textarea")))
        self._add_attribute_strategies(fallback_strategies, locator_value, "//input", ["id", "name", "placeholder"])
        element = self._try_locators(fallback_strategies)

        self._cache_successful_strategy(element, fallback_strategies, cache_key)

        return element

    def _handle_select_fallback(self, locator, input_value):
        locator_type = locator.get("type")
        locator_value = locator.get("value")

        cache_key = f"select_{locator_type}_{locator_value}"
        cached_element = self._try_cached_strategy(cache_key, EC.presence_of_element_located)
        if cached_element:
            return cached_element

        fallback_strategies = []

        if locator_type == "xpath" and "//select" in locator_value:
            self._add_contains_strategy(fallback_strategies, locator_value)
            self._add_custom_select_strategies(fallback_strategies, locator_value, input_value)

        if input_value:
            sanitized_input = self._sanitize_xpath_value(input_value)
            fallback_strategies.append((By.XPATH,
                                        f"//input[@type='radio' and @{locator_type}='{locator_value}' and @value={sanitized_input}]"))

        elif locator_type in ["id", "name"]:
            fallback_strategies += self._check_id_name(locator_type, locator_value, "select", "option")

        self._add_attribute_strategies(fallback_strategies, locator_value, "//select", ["id", "name", "class"])
        element = self._try_locators(fallback_strategies)

        self._cache_successful_strategy(element, fallback_strategies, cache_key)

        return element

    def _handle_wait_visible_fallback(self, locator):
        locator_type = locator.get("type")
        locator_value = locator.get("value")

        cache_key = f"wait_{locator_type}_{locator_value}"
        cached_element = self._try_cached_strategy(cache_key, EC.visibility_of_element_located)
        if cached_element:
            return cached_element

        fallback_strategies = []

        if locator_type == "xpath":
            self._add_contains_strategy(fallback_strategies, locator_value)

            if "//button" in locator_value:
                fallback_strategies.append((By.XPATH, locator_value.replace("//button", "//a")))
                fallback_strategies.append((By.XPATH, locator_value.replace("//button", "//*")))
            elif "//a" in locator_value:
                fallback_strategies.append((By.XPATH, locator_value.replace("//a", "//button")))
                fallback_strategies.append((By.XPATH, locator_value.replace("//a", "//*")))

            text_value = self._extract_text_value(locator_value)
            if text_value:
                sanitized_text = self._sanitize_xpath_value(text_value)
                fallback_strategies.append((By.XPATH, f"//*[contains(text(), {sanitized_text})]"))

        for by_type, locator in fallback_strategies:
            try:
                element = WebDriverWait(self.driver, 3).until(
                    EC.visibility_of_element_located((by_type, locator))
                )
                print(f"Found visible element with fallback locator: {locator}")

                self.strategy_cache[cache_key] = (by_type, locator)

                return element
            except (TimeoutException, NoSuchElementException):
                time.sleep(self.fallback_delay)  # Add delay between attempts
                continue

        return None

    def _handle_link_fallback(self, locator, url):
        print(f"Link element not found. Attempting to navigate directly to: {url}")

        cache_key = f"link_{locator.get('type')}_{locator.get('value')}"
        cached_element = self._try_cached_strategy(cache_key, EC.element_to_be_clickable)
        if cached_element:
            return cached_element

        contains_strategies = []

        sanitized_url = self._sanitize_xpath_value(url)
        contains_strategies.append((By.XPATH, f"//a[contains(@href, {sanitized_url})]"))

        if "/" in url:
            path_part = url.split("/")[-1]
            if path_part:
                sanitized_path = self._sanitize_xpath_value(path_part)
                contains_strategies.append((By.XPATH, f"//a[contains(@href, {sanitized_path})]"))

        locator_value = locator.get("value")
        text_value = self._extract_text_value(locator_value)
        if text_value:
            sanitized_text = self._sanitize_xpath_value(text_value)
            contains_strategies.append((By.XPATH, f"//a[contains(text(), {sanitized_text})]"))

        element = self._try_clickable_locators(contains_strategies)

        self._cache_successful_strategy(element, contains_strategies, cache_key)

        if element:
            return element

        domain, main_domain = self._get_domain_info()
        urls_to_try = []

        if url.startswith('/'):
            if domain:
                urls_to_try.append(f"{domain}{url}")
            if main_domain and main_domain != domain:
                urls_to_try.append(f"{main_domain}{url}")
            urls_to_try.append(f"https:{url}" if url.startswith('//') else f"https://{url.lstrip('/')}")
        elif not url.startswith(('http://', 'https://')):
            if domain:
                urls_to_try.append(f"{domain}/{url.lstrip('/')}")
            if main_domain and main_domain != domain:
                urls_to_try.append(f"{main_domain}/{url.lstrip('/')}")
            urls_to_try.append(f"https://{url}")
        else:
            urls_to_try.append(url)

        if not urls_to_try:
            urls_to_try.append(url)

        return {"urls_to_try": urls_to_try}

    def _try_cached_strategy(self, cache_key, condition_func):
        """Try to use a cached strategy if available"""
        if cache_key in self.strategy_cache:
            print(f"Using cached strategy for {cache_key}")
            by_type, locator_value = self.strategy_cache[cache_key]
            try:
                element = WebDriverWait(self.driver, self.timeout).until(
                    condition_func((by_type, locator_value))
                )
                return element
            except (TimeoutException, NoSuchElementException):
                print("Cached strategy failed, trying other strategies")
                del self.strategy_cache[cache_key]
        return None

    def _add_contains_strategy(self, strategies, locator_value):
        if "=" in locator_value:
            attr_match = re.search(r'\[@([^=]+)=[\'\"]([^\'\"]+)[\'\"]\]', locator_value)
            if attr_match:
                attr_name = attr_match.group(1)
                attr_value = attr_match.group(2)
                element_part = locator_value.split('[')[0]
                contains_xpath = f"{element_part}[contains(@{attr_name}, '{attr_value}')]"
                strategies.append((By.XPATH, contains_xpath))

    def _add_attribute_strategies(self, strategies, locator_value, element_type, attributes):
        for attr in attributes:
            attr_value = self._extract_attribute_value(locator_value, attr)
            if attr_value:
                sanitized_attr = self._sanitize_xpath_value(attr_value)
                strategies.append((By.XPATH, f"{element_type}[@{attr}={sanitized_attr}]"))
                strategies.append((By.XPATH, f"{element_type}[contains(@{attr}, {sanitized_attr})]"))

                for variation in self._generate_case_variations(attr_value):
                    sanitized_variation = self._sanitize_xpath_value(variation)
                    strategies.append((By.XPATH, f"{element_type}[@{attr}={sanitized_variation}]"))
                    strategies.append((By.XPATH, f"{element_type}[contains(@{attr}, {sanitized_variation})]"))

                for part in self._split_identifier(attr_value):
                    if len(part) > 2:
                        sanitized_part = self._sanitize_xpath_value(part)
                        strategies.append((By.XPATH, f"{element_type}[contains(@{attr}, {sanitized_part})]"))

    def _add_case_variation_strategies(self, strategies, locator_type, locator_value, other_type, element_type="*"):
        for variation in self._generate_case_variations(locator_value):
            strategies.append((By.XPATH, f"//{element_type}[@{locator_type}='{variation}']"))
            strategies.append((By.XPATH, f"//{element_type}[contains(@{locator_type}, '{variation}')]"))
            strategies.append((By.XPATH, f"//{element_type}[@{other_type}='{variation}']"))
            strategies.append((By.XPATH, f"//{element_type}[contains(@{other_type}, '{variation}')]"))

        for part in self._split_identifier(locator_value):
            if len(part) > 2:
                strategies.append((By.XPATH, f"//{element_type}[contains(@{locator_type}, '{part}')]"))
                strategies.append((By.XPATH, f"//{element_type}[contains(@{other_type}, '{part}')]"))

    def _add_custom_select_strategies(self, strategies, locator_value, input_value):
        for attr in ["id", "name", "class"]:
            attr_value = self._extract_attribute_value(locator_value, attr)
            if attr_value:
                strategies.append(
                    (By.XPATH, f"//div[contains(@class, 'select') and @{attr}='{attr_value}']"))
                strategies.append(
                    (By.XPATH, f"//div[contains(@class, 'dropdown') and @{attr}='{attr_value}']"))

                if input_value:
                    sanitized_input = self._sanitize_xpath_value(input_value)
                    strategies.append(
                        (By.XPATH, f"//input[@type='radio' and @name='{attr_value}' and @value={sanitized_input}]"))

    def _check_id_name(self, locator_type, locator_value, tag, reserve_tag):
        other_type = "name" if locator_type == "id" or "id" in locator_value else "id"
        current_type = locator_type if locator_type != "xpath" else "name"
        if current_type != locator_type and "id" in locator_value:
            current_type = "id"

        value = self._extract_attribute_value(locator_value, current_type)
        fallback_strategies = [(By.XPATH, f"//{tag}[@{other_type}='{value}']"),
                               (By.XPATH, f"//{tag}[contains(@{other_type}, '{value}')]")]

        self._add_case_variation_strategies(fallback_strategies, current_type, locator_value, other_type, tag)

        if len(reserve_tag) > 0:
            fallback_strategies.append((By.XPATH, f"//{reserve_tag}[@{current_type}='{value}']"))
            fallback_strategies.append((By.XPATH, f"//{reserve_tag}[contains(@{current_type}, '{value}')]"))

        return fallback_strategies

    def _check_separate_words(self, locator_type, locator_value, strategies):
        if locator_type != "xpath":
            return

        span_text_match = re.search(r'//([a-zA-Z0-9_-]+)/span\[contains\(text\(\),\s*[\'\"]([^\'\"]+)[\'\"]\)\]',
                                    locator_value)
        if span_text_match:
            html_tag = span_text_match.group(1)
            text_value = span_text_match.group(2)
            self._process_text_value(html_tag, text_value, strategies, is_child_span=True)

        direct_text_match = re.search(r'//([a-zA-Z0-9_-]+)\[contains\(text\(\),\s*[\'\"]([^\'\"]+)[\'\"]\)\]',
                                      locator_value)
        if direct_text_match:
            html_tag = direct_text_match.group(1)
            text_value = direct_text_match.group(2)
            self._process_text_value(html_tag, text_value, strategies)

        tag_match = re.match(r'//([a-zA-Z0-9_-]+)', locator_value)
        if not tag_match:
            return

        html_tag = tag_match.group(1)
        attributes = self._extract_attributes_from_xpath(locator_value)

        if 'text()' in attributes:
            text_value = attributes['text()']
            self._process_text_value(html_tag, text_value, strategies)

        for attr_name, attr_value in attributes.items():
            if not attr_value or not isinstance(attr_value, str):
                continue

            words = self._extract_words_from_value(attr_value)

            if len(words) > 1:
                print(f"Found separate words in attribute {attr_name}: {words}")
                self._add_attribute_strategies(html_tag, attr_name, words, strategies)

                for word in words:
                    if len(word) > 2:
                        self._add_attribute_strategies(html_tag, attr_name, [word], strategies)

    def _process_text_value(self, html_tag, text_value, strategies, is_child_span=False):
        if not text_value or not isinstance(text_value, str):
            return

        if ' ' in text_value and len(text_value.split()) > 1:
            words = [w for w in text_value.split() if len(w) > 1]
            if len(words) > 1:
                print(f"Found space-separated words in text(): {words}")
                self._add_text_content_strategies(html_tag, words, strategies, is_child_span=is_child_span)

                for word in words:
                    if len(word) > 2:
                        self._add_text_content_strategies(html_tag, [word], strategies, is_child_span=is_child_span)

    def _extract_words_from_value(self, attr_value):
        words = []

        if ' ' in attr_value:
            words.extend([w for w in attr_value.split() if len(w) > 1])

        if '_' in attr_value:
            words.extend([w for w in attr_value.split('_') if len(w) > 1])

        if '-' in attr_value:
            words.extend([w for w in attr_value.split('-') if len(w) > 1])

        if any(c.isupper() for c in attr_value) and not attr_value.isupper():
            first_part = re.findall(r'^[a-z]+', attr_value)
            if first_part and len(first_part[0]) > 1:
                words.append(first_part[0])

            camel_parts = re.findall(r'[A-Z][a-z]*', attr_value)
            words.extend([w.lower() for w in camel_parts if len(w) > 1])

        return list(set(words))

    def _add_text_content_strategies(self, html_tag, words, strategies, is_child_span=False):
        contains_conditions = []
        for word in words:
            if len(word) > 1:
                sanitized_word = self._sanitize_xpath_value(word.lower())
                contains_conditions.append(
                    f"contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), {sanitized_word})")

        if contains_conditions:
            if is_child_span:
                all_words_xpath = f"//{html_tag}/span[{' and '.join(contains_conditions)}]"
                strategies.append((By.XPATH, all_words_xpath))

                parent_text_xpath = f"//{html_tag}[{' and '.join(contains_conditions)}]"
                strategies.append((By.XPATH, parent_text_xpath))
            else:
                all_words_xpath = f"//{html_tag}[{' and '.join(contains_conditions)}]"
                strategies.append((By.XPATH, all_words_xpath))

                self._add_related_tag_strategies(html_tag, contains_conditions, strategies)

            any_tag_xpath = f"//*[{' and '.join(contains_conditions)}]"
            strategies.append((By.XPATH, any_tag_xpath))

    def _add_attribute_strategies(self, html_tag, attr_name, words, strategies):
        contains_conditions = []
        for word in words:
            if len(word) > 1:
                sanitized_word = self._sanitize_xpath_value(word.lower())
                contains_conditions.append(
                    f"contains(translate(@{attr_name}, 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), {sanitized_word})")

        if contains_conditions:
            all_words_xpath = f"//{html_tag}[{' and '.join(contains_conditions)}]"
            strategies.append((By.XPATH, all_words_xpath))

            self._add_related_tag_strategies(html_tag, contains_conditions, strategies)

            any_tag_xpath = f"//*[{' and '.join(contains_conditions)}]"
            strategies.append((By.XPATH, any_tag_xpath))

    def _add_related_tag_strategies(self, html_tag, conditions, strategies):
        related_tags = {
            'button': ['a', 'div', 'span', 'input'],
            'a': ['button', 'div', 'span'],
            'input': ['textarea', 'select', 'div'],
            'select': ['div', 'input', 'ul'],
            'label': ['div', 'span', 'p'],
            'div': ['span', 'button', 'a']
        }

        for related_tag in related_tags.get(html_tag, []):
            related_tag_xpath = f"//{related_tag}[{' and '.join(conditions)}]"
            strategies.append((By.XPATH, related_tag_xpath))


    def _cache_successful_strategy(self, element, strategies, cache_key):
        if element and strategies:
            for i, (by_type, locator_value) in enumerate(strategies):
                if i < len(strategies) - 1:
                    self.strategy_cache[cache_key] = (by_type, locator_value)
                    break

    def _try_locators(self, locator_strategies, element_type="element"):
        for by_type, locator in locator_strategies:
            try:
                print(f"Trying {element_type} locator: {locator}")
                element = WebDriverWait(self.driver, self.timeout).until(
                    EC.presence_of_element_located((by_type, locator))
                )
                print(f"Found {element_type} with locator: {locator}")
                return element
            except (TimeoutException, NoSuchElementException):
                time.sleep(self.fallback_delay)
                continue
        return None

    def _try_clickable_locators(self, locator_strategies, element_type="element"):
        for by_type, locator in locator_strategies:
            try:
                print(f"Trying clickable {element_type} locator: {locator}")
                element = WebDriverWait(self.driver, self.timeout).until(
                    EC.element_to_be_clickable((by_type, locator))
                )
                print(f"Found clickable {element_type} with locator: {locator}")
                return element
            except (TimeoutException, NoSuchElementException):
                time.sleep(self.fallback_delay)
                continue
        return None

    def _sanitize_xpath_value(self, value):
        if not value:
            return value
        if "'" in value and '"' in value:
            parts = value.split("'")
            return "concat('" + "', \"'\", '".join(parts) + "')"
        elif "'" in value:
            return f'"{value}"'
        else:
            return f"'{value}'"

    def _generate_case_variations(self, text):
        case_variations = [text]

        words = text.split()
        if len(words) > 1:
            case_variations.append(text.lower())

            first_cap_rest_lower = words[0].capitalize() + ' ' + ' '.join(w.lower() for w in words[1:])
            if first_cap_rest_lower != text:
                case_variations.append(first_cap_rest_lower)

            if len(words) >= 2:
                first_lower_second_cap = words[0].lower() + ' ' + ' '.join(
                    [words[1].capitalize()] + [w.lower() for w in words[2:]]
                )
                if first_lower_second_cap != text:
                    case_variations.append(first_lower_second_cap)
        else:
            if text.lower() != text:
                case_variations.append(text.lower())

        case_variations = list(dict.fromkeys(case_variations))
        return case_variations

    def _extract_tag_name(self, xpath):
        pattern = r'\/([a-zA-Z0-9_-]+)(?:\[|\/?$|$)'
        matches = re.findall(pattern, xpath)

        if matches:
            return matches[-1]

        return None

    def _extract_attributes_from_xpath(self, xpath_expression):
        attributes = {}

        attr_pattern = r'\[@([^=]+)=[\'\"]([^\'\"]+)[\'\"]\]'
        matches = re.findall(attr_pattern, xpath_expression)
        for attr_name, attr_value in matches:
            attributes[attr_name] = attr_value

        contains_pattern = r'contains\(@([^,]+),\s*[\'\"]([^\'\"]+)[\'\"]\)'
        matches = re.findall(contains_pattern, xpath_expression)
        for attr_name, attr_value in matches:
            attributes[attr_name] = attr_value

        starts_with_pattern = r'starts-with\(@([^,]+),\s*[\'\"]([^\'\"]+)[\'\"]\)'
        matches = re.findall(starts_with_pattern, xpath_expression)
        for attr_name, attr_value in matches:
            attributes[attr_name] = attr_value

        ends_with_pattern = r'ends-with\(@([^,]+),\s*[\'\"]([^\'\"]+)[\'\"]\)'
        matches = re.findall(ends_with_pattern, xpath_expression)
        for attr_name, attr_value in matches:
            attributes[attr_name] = attr_value

        simple_attr_pattern = r'\[([a-zA-Z0-9_-]+)=[\'\"]([^\'\"]+)[\'\"]\]'
        matches = re.findall(simple_attr_pattern, xpath_expression)
        for attr_name, attr_value in matches:
            if attr_name not in ['contains', 'starts-with', 'ends-with', 'text()']:
                attributes[attr_name] = attr_value

        return attributes

    def _extract_attribute_value(self, locator_value, attribute):
        if f"@{attribute}=" in locator_value:
            value = locator_value.split(f"@{attribute}=")[1].split("]")[0].strip("'\"")
            return value

        attributes = self._extract_attributes_from_xpath(locator_value)
        return attributes.get(attribute)

    def _extract_text_value(self, locator_value):
        if "text()=" in locator_value:
            value = locator_value.split("text()=")[1].strip("'\"[]")
            return value
        elif "contains(text()," in locator_value:
            start_index = locator_value.find("contains(text(),") + len("contains(text(),")
            end_index = locator_value.find(")", start_index)
            if 0 < start_index < end_index:
                value = locator_value[start_index:end_index].strip().strip("'\"")
                return value
        return None

    def _get_domain_info(self):
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

    def _generate_case_variations(self, text):
        if not text or not isinstance(text, str):
            return []

        variations = {text, text.lower(), text.upper(), text.capitalize()}

        if any(c.isupper() for c in text) and not text.isupper():
            snake_case = re.sub(r'([A-Z])', lambda x: '_' + x.group(1).lower(), text)
            if snake_case.startswith('_'):
                snake_case = snake_case[1:]
            variations.add(snake_case)
        elif '_' in text:
            camel_case = re.sub(r'_([a-z])', lambda x: x.group(1).upper(), text)
            variations.add(camel_case)

        if '-' in text:
            camel_case = re.sub(r'-([a-z])', lambda x: x.group(1).upper(), text)
            variations.add(camel_case)

            snake_case = text.replace('-', '_')
            variations.add(snake_case)

        return list(variations)

    def _split_identifier(self, identifier):
        """Split an identifier into parts based on common separators"""
        if not identifier or not isinstance(identifier, str):
            return []

        parts = []

        # Split by underscore
        if '_' in identifier:
            parts.extend(identifier.split('_'))

        # Split by dash
        if '-' in identifier:
            parts.extend(identifier.split('-'))

        # Split camelCase
        if any(c.isupper() for c in identifier) and not identifier.isupper():
            # Add the parts split by uppercase letters
            camel_parts = re.findall(r'[A-Z][a-z]*', identifier)
            # Add the first part (before first uppercase)
            first_part = re.findall(r'^[a-z]+', identifier)
            if first_part:
                parts.append(first_part[0])
            parts.extend(camel_parts)

        # Remove duplicates and empty strings
        return [part for part in set(parts) if part]
