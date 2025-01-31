import asyncio
import os
import re
import json
import aiohttp
from typing import List, Optional, Dict
from pydantic import BaseModel, Field, ValidationError, HttpUrl
from langchain_openai import ChatOpenAI
from langchain.schema import HumanMessage
from dotenv import load_dotenv
from async_search import get_clean_pages_texts

load_dotenv()

# Инициализация модели OpenAI
llm = ChatOpenAI(
    api_key=os.getenv('OPENAI_API_KEY'),
    base_url="https://api.proxyapi.ru/openai/v1",
    model="gpt-4o-mini"
)

# =====================
# Precisely Accurate Prompts
# =====================

relevant_search_query = """
Ты - профессиональный поисковый стратег с экспертизой в информационной ретривной оптимизации. Твоя задача - создавать поисковые запросы-ключи, которые точно открывают нужные данные. 

Исходные данные:
Вопрос: {question}

Критерии идеального запроса:
1. **Полное сохранение смысла**: Обязательно включи все ключевые элементы вопроса (числа, даты, уникальные названия)
2. **Структурный паттерн**: [Событие/организация] [Искомый факт] [Конкретизирующие параметры] [Год]
3. **Приоритет официальных терминов**: Используй формулировки из вопроса, предполагающие официальные источники ("расписание", "официальный график", "утвержденные даты")
4. **Исключи дубли**: Не повторяй синонимы, выбери наиболее эффективную формулировку
5. **Оптимальная длина**: 5-15 смысловых единиц, соединенных пробелами

Примеры хороших запросов:
- "мегашкола итмо официальное расписание основной этап январь 2025"
- "утвержденные даты основного этапа мегашколы итмо 2025"

Примеры плохих запросов:
- "даты мегашколы" (неполный)
- "мероприятия итмо 2025" (нет этапа)
- "когда мегашкола январь" (неформально)
- "мегашкола итмо 2025 график мероприятий январь основной этап"

Сгенерируй ТОЛЬКО ОДИН оптимальный поисковый запрос без кавычек и пунктуации.
"""

edit_search_query = """
Ты - поисковый аналитик уровня Senior с компетенцией в query refinement. Твоя роль - проводить диагностику неудачных запросов и перепроектировать их с учетом поведенческих факторов поисковых систем.
Вопрос: {question}  

Предыдущий поисковой запрос не выдал нужных результатов: {search_query}

Обрати внимание на:  
- Ключевые слова и смысловые единицы вопроса  
- Возможные перефразировки, делающие запрос более точным  
- Исключение лишних или двусмысленных слов  
- Уточнение специфики, если вопрос общий  

Выведи только готовый поисковый запрос.
"""

summary_by_question = """
Ты - AI-аналитик информации 4-го уровня с сертификацией CRTA (Contextual Relevance & Text Analysis). Твоя миссия - экстрагировать факты с хирургической точностью.

Ролевой профиль:
- Спецтехника: метод "Контекстуального скальпеля"
- Принципы работы:
  * Zero-tolerance к ментальным прыжкам
  * Обязательная проверка кросс-референсов
  * Жесткий приоритет первичных данных

Вопрос: {question}  

Контент (фрагмент):  
{content}  

Шаги для выполнения:  
1. Внимательно проанализируй вопрос. Определи его суть.  
2. Изучи представленный контент, выделяя факты, относящиеся к вопросу.  
3. Игнорируй нерелевантные или второстепенные детали.  
4. Будь внимателен к целевому вопросу, не путай схожие термины, будь предельно точен в формулировках
5. Структурируй ответ четко и емко, сохраняя объективность.  

Выведи важную информацию из контента, которая поможет ответить на вопрос. Если релевантной информации нету, так и напиши.
"""

# =====================
# Structured Models
# =====================

class SearchQuery(BaseModel):
    coT: list[str] = Field(
        description="Пошаговый анализ контента и взаимосвязи с вопросом, выделение данных для точного ответа на вопрос")
    search_query: str = Field(description="Чистый поисковый запрос без упоминания вариантов ответа")

class ContentSummary(BaseModel):
    coT: list[str] = Field(
        description="Пошаговый анализ контента и взаимосвязи с вопросом, выделение данных для точного ответа на вопрос")
    summary: str = Field(description="Точная часть контента, связанная с вопросом.")
    source: str = Field(description="http url источника информации, формат HttpUrl")

class AnswerResponse(BaseModel):
    reasoning: str = Field(description="Проанализируй информацию и выбери правильный вариант ответа.")
    is_answer_clear: bool = Field(description="Действительно ли выбранный тобой ответ кажется тебе прозрачным")
    sources: List[str] = Field(description="http url источников данных, которые были использованы для точного ответа, формат HttpUrl")
    answer: Optional[int] = None
    id: int

# =====================
# Helper Functions
# =====================

def validate_mcq(query: str) -> Optional[List[int]]:
    """Валидация формата вопроса"""
    matches = re.findall(r"(\d+)\.", query)
    options = [int(match) for match in matches]
    return options if len(options) >= 2 and all(1 <= opt <= 10 for opt in options) else None

# =====================
# LLM Chains
# =====================

async def generate_search_query(question: str) -> str:
    """Генерация поискового запроса с StructuredOutput"""
    chain = llm.with_structured_output(SearchQuery)
    result = await chain.ainvoke([HumanMessage(content=relevant_search_query.format(question=question))])
    return result.search_query

async def regenerate_search_query(question: str, search_query: str) -> str:
    """Генерация поискового запроса с StructuredOutput"""
    chain = llm.with_structured_output(SearchQuery)
    result = await chain.ainvoke(
        [HumanMessage(content=edit_search_query.format(question=question, search_query=search_query))])
    return result.search_query

async def summarize_single_content(question: str, content: str, url: str) -> ContentSummary:
    """Helper to summarize a single content piece."""
    chain = llm.with_structured_output(ContentSummary)
    try:
        summary = await chain.ainvoke(
            [HumanMessage(content=summary_by_question.format(question=question, content=content[:5000]))])
        return ContentSummary(coT=summary.coT, summary=summary.summary, source=url)
    except Exception as e:
        return ContentSummary(
            coT=["Ошибка"],
            summary=f"Ошибка суммаризации: {str(e)}",
            source=url
        )

async def summarize_content(question: str, search_results: List[Dict]) -> List[ContentSummary]:
    """Суммаризация контента с StructuredOutput в параллельном режиме"""
    tasks = []
    for result in search_results:
        url, content = result[0], result[1]
        if content:
            tasks.append(summarize_single_content(question, content, url))
    # Run all summary tasks concurrently
    summaries = await asyncio.gather(*tasks, return_exceptions=False)
    return summaries

async def synthesize_answer(question: str, summaries: List[ContentSummary], mcq_options: List[int],
                            request_id: int) -> Dict:
    """Генерация финального ответа с StructuredOutput"""
    chain = llm.with_structured_output(AnswerResponse)
    try:
        result = await chain.ainvoke([HumanMessage(
            content=f"""
Ты — senior fact-checker международного аналитического агентства. Твоя задача — проводить аудит информации 
по строгому протоколу Due Diligence для финансовых отчетов. Твои решения влияют на стратегические решения компаний.

Принципы работы:
1. Режим «Нулевого доверия»: любое утверждение требует двойного подтверждения из источников
2. Приоритет первичных данных: работа только с явно указанными фактами
3. Протокол расхождений: автоматическое вето при любых противоречиях
4. Документированная трассировка: каждая часть ответа должна иметь явную ссылку на источник

Аналитический кейс:

Вопрос: {question}

Доступные варианты ответа: 
{mcq_options}

Релевантная информация из источников:
{json.dumps([[s.source, s.summary] for s in summaries], indent=2)}

Требования к анализу:
1. Тщательно сравни каждое числовое значение, дату или точный факт из источников с вариантами ответов
2. Выбор возможен ТОЛЬКО если есть точное совпадение формулировки в проверяемом источнике
3. Запрещено делать предположения, интерполяции или выбирать "ближайший" вариант
4. Если несколько источников противоречат друг другу - вернуть null
5. Если информация отсутствует/неполная/неоднозначная - вернуть null

Шаги формирования ответа:
"Анализ": 
[
"Поиск точных соответствий для каждого варианта в источниках",
"Проверка противоречий между источниками",
"Оценка полноты информации"
],

"Выбор опции": "ТОЛЬКО номер варианта при 100% совпадении",
"Выбор источников, с которых взят ответ": "Цитата из источника с подтверждением",
"is_answer_clear": True или False - твоя уверенность в ответе,
"""
        )])
        result.id = request_id
        result.sources = result.sources[:3]  # Ограничиваем количество источников
        return result.model_dump()

    except ValidationError as e:
        return AnswerResponse(
            id=request_id,
            answer=None,
            reasoning=f"Ошибка валидации ответа: {str(e)}",
            is_answer_clear=False,
            sources=[]
        ).model_dump()

# =====================
# Main Flow
# =====================

async def answer_mcq(input_data: dict) -> Dict:
    question = input_data.get("query", "")
    request_id = input_data.get("id", 0)

    # Валидация формата вопроса
    mcq_options = validate_mcq(question)
    if not mcq_options:
        return AnswerResponse(
            id=request_id,
            answer=None,
            reasoning="Некорректный формат вопроса с вариантами ответов",
            is_answer_clear=False,
            sources=[]
        ).model_dump()

    try:
        search_query = ''
        for count in range(4):
            # Генерация поискового запроса
            if not search_query:
                search_query = await generate_search_query(question)
            else:
                search_query = await regenerate_search_query(question, search_query)

            print("Current search query:", search_query)

            # Получение данных (предполагается, что get_clean_pages_texts уже оптимизирован для асинхронного вызова)
            search_results = await get_clean_pages_texts(search_query)

            # Параллельная суммаризация результатов
            summaries = await summarize_content(question, search_results)

            # Синтез ответа
            answer = await synthesize_answer(question, summaries, mcq_options, request_id)

            if answer.get("is_answer_clear"):
                return answer  # Ранний выход если ответ ясен

        # Если ни одна итерация не дала ясный ответ, возвращаем последний результат
        return answer

    except Exception as e:
        return AnswerResponse(
            id=request_id,
            answer=None,
            reasoning=f"Ошибка обработки: {str(e)}",
            is_answer_clear=False,
            sources=[]
        ).model_dump()

async def main():
    sample_input = {
        "query": "На какие даты приходится проведение основного этапа МегаШколы ИТМО в январе 2025 года?\n1. 11-13\n2. 23-25\n3. 28-30\n4. 29-31",
        "id": 3
    }
    response = await answer_mcq(sample_input)
    print(json.dumps(response, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    asyncio.run(main())
