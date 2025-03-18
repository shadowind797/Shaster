import re
from pathlib import Path
from typing import List, Optional


def extract_urls_from_markdown(file_path: str) -> List[str]:
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    if path.suffix.lower() != '.md':
        raise ValueError(f"File is not a Markdown file: {file_path}")

    with open(file_path, 'r', encoding='utf-8') as file:
        content = file.read()

    url_pattern = r'https?://[^\s"\'\)\]<>]+(?:\([^\s]+\)|[^\s"\'\)\]<>])*'
    urls = re.findall(url_pattern, content)

    return urls


def get_urls(test_case_file):
    try:
        urls = extract_urls_from_markdown(test_case_file)
        unique_urls = []
        seen = set()

        for url in urls:
            if url not in seen:
                seen.add(url)
                unique_urls.append(url)

        print(f"Found {len(unique_urls)} URLs in {test_case_file}:")
        for url in unique_urls:
            print(f"- {url}")
        return unique_urls
    except (FileNotFoundError, ValueError) as e:
        print(f"Error: {e}")
