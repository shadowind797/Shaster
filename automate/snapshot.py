import os
import requests
from urllib.parse import urlparse
import hashlib
from pathlib import Path

import os
import requests
from urllib.parse import urlparse
import hashlib
from pathlib import Path
from bs4 import BeautifulSoup


def fetch_and_save_html(url, output_dir="../data/snaps/"):
    try:
        Path(output_dir).mkdir(parents=True, exist_ok=True)

        parsed_url = urlparse(url)
        domain = parsed_url.netloc
        path = parsed_url.path.strip('/')

        url_hash = hashlib.md5(url.encode()).hexdigest()[:8]

        if path:
            filename = f"{domain}_{path.replace('/', '_')}_{url_hash}.html"
        else:
            filename = f"{domain}_{url_hash}.html"

        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) '
                          'Chrome/91.0.4472.124 Safari/537.36'
        }
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, 'html.parser')
        body_tag = soup.body

        body_content = str(body_tag) if body_tag else response.text

        file_path = os.path.join(output_dir, filename)
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(body_content)

        print(f"Successfully saved HTML body from {url} to {file_path}")
        return file_path

    except requests.exceptions.RequestException as e:
        print(f"Error fetching URL {url}: {e}")
        return None
    except IOError as e:
        print(f"Error saving HTML to file: {e}")
        return None
    except Exception as e:
        print(f"Unexpected error: {e}")
        return None


def get_page_snap(url):
    snap = fetch_and_save_html(url)
    return snap
