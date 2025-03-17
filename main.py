
from google import genai
import os
import mimetypes
import base64
import json

from google.genai import types

from automate.automate import run_test
from automate.snapshot import get_page_snap
from automate.refs import get_urls

client = genai.Client(api_key="AIzaSyBzVy4mva2mc5CkA6oCMcxeULtLNRzDGk4")


def get_file_mime_type(file_path):
    mime_type, _ = mimetypes.guess_type(file_path)

    if not mime_type:
        if file_path.lower().endswith('.md'):
            mime_type = 'text/markdown'
        elif file_path.lower().endswith('.html'):
            mime_type = 'text/html'

    return mime_type or 'application/octet-stream'


def create_file_part(file_path):
    if not os.path.exists(file_path):
        print(f"Warning: File not found at path: {file_path}")
        return None

    mime_type = get_file_mime_type(file_path)

    with open(file_path, 'rb') as f:
        file_data = f.read()

    # Convert binary data to base64 string
    file_data_b64 = base64.b64encode(file_data).decode('utf-8')

    return {
        "inline_data": {
            "mime_type": mime_type,
            "data": file_data_b64
        }
    }


def process_with_multiple_attachments(md_file_path, html_file_paths,
                                      prompt=""):
    try:
        parts = [{"text": prompt}]

        if md_file_path:
            md_part = create_file_part(md_file_path)
            if md_part:
                parts.append(md_part)

        html_count = 0
        for html_file_path in html_file_paths:
            if html_file_path:
                html_part = create_file_part(html_file_path)
                if html_part:
                    parts.append(html_part)
                    html_count += 1

        if len(parts) == 1:
            return "Error: No valid files were provided."

        content = {
            "role": "user",
            "parts": parts
        }

        enhanced_prompt = """
        You are a highly skilled test automation engineer. Your task is to convert human-readable test cases and HTML snapshots into a precise JSON test suite that can be used to automate browser tests.

        **KNOWLEDGE BASE:**
        The .html files are snapshots of pages that you will use to automating (they provided in order, so if you can't find element in first HTML it must be in second).
        When step requires input of possible-uniq data (username, email), generate a combination of random numbers or/and letters (sfih5$gdu2, hiefueg9658@gmail.com).
        When step requires input of an email, use the outlook.com domain.
        Any password you generate should be longer than 12 characters.

        While identifying elements keep in mind that:
        Words 'enter' or 'input' more likely refers to <input/> tag
        Words 'select' or 'pick' more likely refers to <input type='select/radio' /> tag or <select/> dropdown
        Phrase 'check ... field' more likely refers to <input type='radio/checkbox' /> tag

        Make difference between <button/> that redirects to another page and <a/> tag.
        Make difference between @name='displayname' and @name='displayName'.
        Never identify: <input/> with @placeholder, any element with 'data-encore-id'.
        Always identify: <a/> with @href, <button/> with @data-testid or @text.
        
        Do not stop generating steps even if you not certain in your answer

        **Finding the Element (PRIMARY FOCUS):** For EACH test step, your primary task is to find the HTML element that *best corresponds* to the action described in the step.

        The JSON should follow this exact pattern:
        ```json
        [{
          "testName": "|Name of test case|",
          "steps": [{
            "action": "|Action type. Possible values: 'click', 'goto', 'input', 'select', 'waitForElementVisible', 'waitForRedirect'|",
            "locator": {
              "type": "|Locator type. Possible values: 'id', 'css', 'url', 'xpath'|",
              "value": "|Locator value from the HTML - EXACT MATCH|"
            },
            "input_value": "|Value of input. Appears only if action is input or select|",
          }]
        }]
        ```

        EXAMPLE 1:
        Test Case: "Click the 'Log in' button."
        HTML: <button class="login-button primary"><span>Log in</span></button>
        JSON: [{
          "testName": "Example Test",
          "steps": [{
            "action": "click",
            "locator": {
              "type": "xpath",
              "value": "//button[text()='Log in']"
            }
          }]
        }]

        EXAMPLE 2:
        Test Case: "Enter any password into Password field"
        HTML: <input id="new-password" name="new-password" type="password" autocomplete="new-password" />
        JSON: [{
          "testName": "Example Test",
          "steps": [{
            "action": "input",
            "locator": {
              "type": "xpath",
              "value": "//input[@name='new-password']"
            },
            "input_value": "pas%sword142!@#"
          }]
        }]

        Now, process the following test case and HTML:
        """

        parts[0]["text"] = enhanced_prompt

        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=content,
            config=types.GenerateContentConfig(
                temperature=0,
                top_p=0.5,
                top_k=40,
                max_output_tokens=8192,
            )
        )

        return response.text
    except Exception as e:
        return f"Error processing with Gemini: {str(e)}"


def save_response_to_json(response, test_case_path):
    output_dir = "./data/autos/"
    os.makedirs(output_dir, exist_ok=True)

    if test_case_path:
        base_filename = os.path.basename(test_case_path)
        filename = os.path.splitext(base_filename)[0] + ".json"
    else:
        filename = "gemini_response.json"

    output_path = os.path.join(output_dir, filename)

    try:
        json_data = json.loads(response)
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(json_data, f, indent=2)
    except json.JSONDecodeError:
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump({"response": response}, f, indent=2)

    return filename


def get_snapshots_from_urls(urls):
    snapshots = []
    for url in urls:
        print(f"Getting snapshot for URL: {url}")
        snapshot = get_page_snap(url)
        if snapshot:
            snapshots.append(snapshot)
    return snapshots


run = True
while run:
    test_case_md = input("Provide test case file path: ")
    initial_url = input("Provide initial page URL (optional if URLs are in the markdown): ")

    if not test_case_md and not initial_url:
        print("Error: Either a markdown file or an initial URL must be provided.")
        continue

    valid_files = True
    if test_case_md and not os.path.exists(test_case_md):
        print(f"Error: Markdown file not found at path: {test_case_md}")
        valid_files = False

    if not valid_files:
        continue

    urls = []
    if test_case_md:
        print(f"Extracting URLs from: {test_case_md}")
        extracted_urls = get_urls(test_case_md)
        if extracted_urls:
            urls.extend(extracted_urls)

    if initial_url and initial_url not in urls:
        urls.append(initial_url)

    if not urls:
        print("Error: No URLs found in markdown file and no initial URL provided.")
        continue

    page_snapshots = get_snapshots_from_urls(urls)

    if not page_snapshots:
        print("Error: Failed to get any HTML snapshots.")
        continue

    print("Processing files:")
    if test_case_md:
        print(f"- Test Case: {test_case_md}")
    print(f"- URLs processed: {len(urls)}")
    print(f"- HTML snapshots: {len(page_snapshots)}")

    result = process_with_multiple_attachments(test_case_md, page_snapshots)
    if len(result) > 10:
        result = result[7:-3]
    output_file = save_response_to_json(result, test_case_md)
    print(f"\nResponse saved to: {output_file}\n")
    print("Processing response...\n")

    print("--- Selenium Test Suit ---")
    run_test(output_file)
    print("--- Selenium Test Suit End ---\n")

    continue_run = input("Continue? (y/n): ").lower()
    run = continue_run == 'y'
