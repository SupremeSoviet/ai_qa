import time
from typing import List
from agent_entrypoint import answer_mcq
from fastapi import FastAPI, HTTPException, Request, Response
from pydantic import HttpUrl
from schemas.request import PredictionRequest, PredictionResponse
# from utils.logger import setup_logger
from logging import Logger
# Initialize
app = FastAPI()
logger = Logger('main')

# @app.on_event("startup")
# async def startup_event():
#     global logger
#     logger = await setup_logger()


@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = time.time()

    body = await request.body()
    logger.info(
        f"Incoming request: {request.method} {request.url}\n"
        f"Request body: {body.decode()}"
    )

    response = await call_next(request)
    process_time = time.time() - start_time

    response_body = b""
    async for chunk in response.body_iterator:
        response_body += chunk

    logger.info(
        f"Request completed: {request.method} {request.url}\n"
        f"Status: {response.status_code}\n"
        f"Response body: {response_body.decode()}\n"
        f"Duration: {process_time:.3f}s"
    )

    return Response(
        content=response_body,
        status_code=response.status_code,
        headers=dict(response.headers),
        media_type=response.media_type,
    )


@app.post("/api/request", response_model=PredictionResponse)
async def predict(body: PredictionRequest):
    try:
        logger.info(f"Processing prediction request with id: {body.id}")

        temp_dict_to_pass_into_model = {
            'id': body.id,
            'query': body.query
        }

        full_answer = await answer_mcq(temp_dict_to_pass_into_model)  # Замените на реальный вызов модели

        try:
            response = PredictionResponse(
                id=body.id,
                answer=full_answer['answer'],
                reasoning='Ответ сгенерирован при помощи gpt4o-mini; ' + full_answer['reasoning'],
                sources=full_answer['sources'],
            )

            logger.info(f"Successfully processed request {body.id}")
            return response
        except:
            response = PredictionResponse(
                id=body.id,
                answer=full_answer['answer'],
                reasoning='Ответ сгенерирован при помощи gpt4o-mini; ' + full_answer['reasoning'],
                sources=[],
            )

            logger.info(f"Successfully processed request {body.id}")
            return response

    except ValueError as e:
        error_msg = str(e)
        logger.error(f"Validation error for request {body.id}: {error_msg}")
        raise HTTPException(status_code=400, detail=error_msg)
    except Exception as e:
        logger.error(f"Internal error processing request {body.id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")