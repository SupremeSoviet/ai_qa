# LLM Agent & FastAPI Search & Parsing Service

[![Python Version](https://img.shields.io/badge/Python-3.12.4%2B-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-v0.115.8-blue.svg)](https://fastapi.tiangolo.com/)
[![Yandex Search API](https://img.shields.io/badge/Yandex_Search_API-XML--based-orange.svg)](https://yandex.com/dev/xml/)
[![Beautiful Soup](https://img.shields.io/badge/Beautiful_Soup-v4.12.3-green.svg)](https://www.crummy.com/software/BeautifulSoup/)
[![OpenAI](https://img.shields.io/badge/OpenAI-API-blue.svg)](https://openai.com/)
[![Pydantic](https://img.shields.io/badge/Pydantic-v2.10.6-blue.svg)](https://pydantic-docs.helpmanual.io/)

## О проекте

Этот проект представляет собой асинхронного агента на базе LLM, который:
- **Генерирует поисковые запросы** для извлечения релевантного контента;
- **Использует Yandex Search API** для получения данных;
- **Парсит и суммирует полученный контент** с помощью инструментов `aiohttp`, `lxml` и `xml.etree.ElementTree`;
- **Синтезирует финальный ответ** на основе агрегированной информации;
- **Обрабатывает запросы через FastAPI** для обеспечения быстрого и масштабируемого API-сервиса.

## Архитектура проекта

Проект состоит из следующих основных компонентов:

- **LLM Agent**  
  Основной код агента, который использует модель `gpt-4o-mini` для генерации поисковых запросов, суммаризации контента и синтеза окончательного ответа. Все запросы к модели выполняются асинхронно с использованием `asyncio`.

- **Yandex Search API & Парсинг**  
  Модуль, реализующий взаимодействие с Yandex Search API. Данные, полученные от API, парсятся с использованием библиотек `aiohttp`, `lxml` и `xml.etree.ElementTree` для последующего анализа и суммаризации.

- **FastAPI App**  
  Веб-сервис, созданный с использованием FastAPI, который предоставляет HTTP endpoint для отправки запросов. Валидация входящих данных, логирование запросов и обработка ошибок реализованы на уровне middleware и роутов.

## Зависимости

Для корректной работы проекта необходим .env файл, содержащий _OPENAI_API_KEY_, _YANDEX_SEARCH_SECRET_, _YANDEX_USER_ID_

_YANDEX_USER_ID_ - id of yandex cloud folder

_YANDEX_SEARCH_SECRET_ - api-key of service account with search_api.execute permission

_OPENAI_API_KEY_ - OpenAI api-key

## Сборка
Для запуска выполните команду:

```bash
docker-compose up -d
```
Она соберёт Docker-образ, а затем запустит контейнер.

После успешного запуска контейнера приложение будет доступно на http://localhost:8080.

## Проверка работы
Отправьте POST-запрос на эндпоинт /api/request. Например, используйте curl:

```bash
curl --location --request POST 'http://localhost:8080/api/request' \
--header 'Content-Type: application/json' \
--data-raw '{
  "query": "В каком городе находится главный кампус Университета ИТМО?\n1. Москва\n2. Санкт-Петербург\n3. Екатеринбург\n4. Нижний Новгород",
  "id": 1
}'
```
В ответ вы получите JSON вида:

```json
{
  "id": 1,
  "answer": 1,
  "reasoning": "Из информации на сайте",
  "sources": [
    "https://itmo.ru/ru/",
    "https://abit.itmo.ru/"
  ]
}
```
