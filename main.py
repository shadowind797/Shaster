from google import genai
import os
import mimetypes
import base64
import json

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


def process_with_multiple_attachments(md_file_path, html_file_path,
                                      prompt="There are the test case in attached .md file and the page snapshot in attached .html file.\n"):
    try:
        parts = [{"text": prompt}]

        if md_file_path:
            md_part = create_file_part(md_file_path)
            if md_part:
                parts.append(md_part)

        if html_file_path:
            html_part = create_file_part(html_file_path)
            if html_part:
                parts.append(html_part)

        if len(parts) == 1:
            return "Error: No valid files were provided."

        content = {
            "role": "user",
            "parts": parts
        }

        json_prompt = prompt + (
            "\n\nPlease format your response as valid JSON instructions "
            "to executable file that will test this page in that particular format provided below without any additional text. "
            "(if some fields are null or empty string you should not include them to answer)")
        json_prompt += ("\n\n[{'testName': 'button click test','steps': ["
                        "{'action': 'click'',"
                        "'locator': {'type': 'id','value': 'rightBtn'},"
                        "'input_value': '',}]}]")
        json_prompt += ("\n\nThere are the ONLY possible values of fields: "
                        "{'action': ['click', 'goto', 'input', 'waitForElementVisible'],"
                        "'locator': {'type': ['id', 'xpath', 'cssSelector', 'url']}}")
        parts[0]["text"] = json_prompt

        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=content
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

    return output_path


run = True
while run:
    test_case_md = input("Provide test case file path (or press Enter to skip): ")
    page_snapshot = input("Provide page snapshot path (or press Enter to skip): ")

    if not test_case_md and not page_snapshot:
        print("Error: At least one file path must be provided.")
        continue

    valid_files = True
    if test_case_md and not os.path.exists(test_case_md):
        print(f"Error: Markdown file not found at path: {test_case_md}")
        valid_files = False

    if page_snapshot and not os.path.exists(page_snapshot):
        print(f"Error: HTML file not found at path: {page_snapshot}")
        valid_files = False

    if not valid_files:
        continue

    print("Processing files:")
    if test_case_md:
        print(f"- Test Case: {test_case_md}")
    if page_snapshot:
        print(f"- Page: {page_snapshot}")

    result = process_with_multiple_attachments(test_case_md, page_snapshot)
    if len(result) > 10:
        result = result[7:-3]
    output_file = save_response_to_json(result, test_case_md)
    print(f"\nResponse saved to: {output_file}")

    continue_run = input("Continue? (y/n): ").lower()
    run = continue_run == 'y'
