import asyncio
import aiohttp
import lxml.html
import xml.etree.ElementTree as ET
import re
import os
from dotenv import load_dotenv

load_dotenv()

# Precompile all regex patterns
MULTI_NEWLINES = re.compile(r'\n{3,}')
MULTI_SPACES = re.compile(r'[ \t\f\r]{2,}')
UNWANTED_NEWLINES = re.compile(r'\n\s*\n')
NON_BREAKING_SPACE = re.compile(r'\xa0')
CLEAN_NEWLINES = re.compile(r'\n')


def extract_clean_text_lxml(html):
    """Fast HTML text extraction using lxml"""
    tree = lxml.html.fromstring(html)

    # Remove unwanted tags
    for elem in tree.xpath('//script|//style|//meta|//link|//head|//noscript|//button|//footer|//form|//iframe'):
        elem.getparent().remove(elem)

    # Extract text
    text = tree.text_content()

    # Apply optimized regex cleaning
    text = MULTI_NEWLINES.sub('\n\n', text)
    text = MULTI_SPACES.sub(' ', text)
    text = NON_BREAKING_SPACE.sub(' ', text)
    return text.strip()


async def fetch_page_html(session, url):
    """Fetch HTML asynchronously with optimized timeouts"""
    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=10),
                               allow_redirects=True) as response:
            response.raise_for_status()
            return await response.text()
    except Exception:
        return None


async def process_url(session, url, max_length=1000):
    """Process a single URL asynchronously"""
    html = await fetch_page_html(session, url)
    if not html:
        return None

    try:
        clean_text = extract_clean_text_lxml(html)
        clean_text = UNWANTED_NEWLINES.sub(' ', clean_text)
        clean_text = CLEAN_NEWLINES.sub(' ', clean_text).strip()

        return (
            url, clean_text[:max_length] + '...' if len(clean_text) > max_length else clean_text
        ) if clean_text else None
    except Exception:
        return None


async def async_get_search_results(query, folder_id, api_key):
    """Async search request to Yandex XML API"""
    base_url = 'https://yandex.ru/search/xml'
    params = {
        'folderid': folder_id,
        'apikey': api_key,
        'query': query,
        'sortby': 'rlv',
        'groupby': 'attr=d.mode=deep.groups-on-page=10.docs-in-group=1'
    }

    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=15)) as session:
        async with session.get(base_url, params=params) as response:
            response.raise_for_status()
            content = await response.text()
            return ET.fromstring(content)


async def get_clean_pages_texts(query, max_results=5):
    """Fetch and process search results asynchronously"""
    folder_id = os.getenv('YANDEX_SEARCH_ID')
    api_key = os.getenv('YANDEX_SEARCH_SECRET')

    root = await async_get_search_results(query, folder_id, api_key)
    if not root:
        return []

    urls = [url.text for group in root.findall(".//group")
            for url in group.findall("./doc/url")][:max_results]

    connector = aiohttp.TCPConnector(limit_per_host=50)
    async with aiohttp.ClientSession(
            connector=connector,
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"}
    ) as session:
        tasks = [process_url(session, url) for url in urls]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        return [r for r in results if r and not isinstance(r, Exception)][:max_results]
