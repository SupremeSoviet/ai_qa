import requests
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

def fetch_page_html(url):
    """Получение HTML-кода страницы с обработкой ошибок"""
    try:
        page_response = requests.get(url,
                                     timeout=10,
                                     headers={
                                         "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"},
                                     allow_redirects=True)
        page_response.raise_for_status()
        return page_response.text
    except Exception as e:
        return None

def get_search_results(query, folder_id, api_key):
    """Выполнение поискового запроса через Яндекс.XML"""
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

def get_clean_pages_texts(query, max_results=10):
    """Основная функция для получения чистых текстов страниц"""
    folder_id = os.getenv('YANDEX_SEARCH_ID')
    api_key = os.getenv('YANDEX_SEARCH_SECRET')

    # Получаем результаты поиска
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

    # Собираем URL и тексты страниц
    pages_info = []
    for url in urls[:max_results]:
        html = fetch_page_html(url)
        if html:
            try:
                clean_text = extract_clean_text(html)
                # Дополнительная обработка текста
                clean_text = re.sub(r'\n\s*\n', ' ', clean_text)
                clean_text = re.sub(r'\n', ' ', clean_text)
                clean_text = clean_text.strip()
                if clean_text:
                    pages_info.append([url, clean_text])
            except Exception as e:
                continue
        if len(pages_info) >= max_results:
            break

    return pages_info[:max_results]

results = get_clean_pages_texts('Где находится университет ИТМО?')

for idx, (url, text) in enumerate(results, 1):
    print(f"\n{'='*80}\nРезультат {idx}:\nСсылка: {url}\nТекст:")
    print(text[:1000] + '...' if len(text) > 1000 else text)