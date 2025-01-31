import asyncio
import requests
import aiohttp
import xml.etree.ElementTree as ET
from bs4 import BeautifulSoup
import re
import os
from dotenv import load_dotenv

load_dotenv()


def extract_clean_text(html):
    """Извлечение и очистка текста из HTML с сохранением структуры"""
    soup = BeautifulSoup(html, 'html.parser')

    # Удаляем ненужные элементы
    for element in soup(['script', 'style', 'meta', 'link', 'head', 'noscript', 'button', 'footer', 'form', 'iframe']):
        element.decompose()

    # Заменяем структурные элементы на переносы строк
    replacements = {
        'br': '\n',
        'p': '\n',
        'div': '\n',
        'section': '\n',
        'article': '\n',
        'li': '\n• ',
        'h1': '\n\n', 'h2': '\n\n', 'h3': '\n\n', 'h4': '\n\n', 'h5': '\n\n', 'h6': '\n\n'
    }

    for tag, replacement in replacements.items():
        for element in soup.find_all(tag):
            element.append(replacement)

    # Извлекаем текст с сохранением пробелов
    text = soup.get_text(separator='\n', strip=False)

    # Обработка специальных символов и форматирования
    text = re.sub(r'\n{3,}', '\n\n', text)  # Удаляем лишние переносы
    text = re.sub(r'[ \t\f\r]{2,}', ' ', text)  # Заменяем множественные пробелы
    text = re.sub(r'\xa0', ' ', text)  # Заменяем неразрывные пробелы
    text = text.strip()

    return text


async def fetch_page_html(session, url):
    """Асинхронное получение HTML-кода страницы"""
    try:
        async with session.get(url, timeout=10, allow_redirects=True) as response:
            response.raise_for_status()
            return await response.text()
    except Exception as e:
        return None


async def process_url(session, url, max_length=1000):
    """Асинхронная обработка одного URL"""
    html = await fetch_page_html(session, url)
    if not html:
        return None

    try:
        clean_text = extract_clean_text(html)
        # Дополнительная обработка текста
        clean_text = re.sub(r'\n\s*\n', ' ', clean_text)
        clean_text = re.sub(r'\n', ' ', clean_text).strip()

        if not clean_text:
            return None

        return (url, clean_text[:max_length] + '...' if len(clean_text) > max_length else clean_text)
    except Exception as e:
        return None


def get_search_results(query, folder_id, api_key):
    """Синхронная функция выполнения поискового запроса через Яндекс.XML"""
    base_url = 'https://yandex.ru/search/xml'
    params = {
        'folderid': folder_id,
        'apikey': api_key,
        'query': query,
        'sortby': 'rlv',
        'groupby': 'attr=d.mode=deep.groups-on-page=10.docs-in-group=1'
    }

    try:
        response = requests.get(base_url, params=params, timeout=15)
        response.raise_for_status()
        root = ET.fromstring(response.content)
        return root
    except Exception as e:
        return None


async def get_clean_pages_texts(query, max_results=5):
    """Основная асинхронная функция для получения чистых текстов"""
    folder_id = os.getenv('YANDEX_SEARCH_ID')
    api_key = os.getenv('YANDEX_SEARCH_SECRET')

    # Получаем результаты поиска (синхронный вызов)
    root = get_search_results(query, folder_id, api_key)
    if not root:
        return []

    # Парсим URL из результатов
    urls = []
    for group in root.findall(".//group"):
        if len(urls) >= max_results:
            break
        doc = group.find("./doc")
        if doc is not None:
            url_element = doc.find("./url")
            if url_element is not None and url_element.text:
                urls.append(url_element.text)

    # Создаем сессию для асинхронных запросов
    async with aiohttp.ClientSession(
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"}
    ) as session:
        # Создаем задачи для параллельной обработки
        tasks = [process_url(session, url) for url in urls[:max_results]]
        results = await asyncio.gather(*tasks)

        # Фильтруем неудачные результаты
        return [result for result in results if result is not None][:max_results]
