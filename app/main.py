from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from .database import Base, engine
from .routes import router


@asynccontextmanager
async def lifespan(app):
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(title="Payment Requests API", lifespan=lifespan)
app.include_router(router)


@app.exception_handler(RequestValidationError)
async def validation_error(request, exc):
    problems = []
    for error in exc.errors():
        if error["type"] == "json_invalid":
            problems.append("body: the request body is not valid JSON")
        else:
            field = ".".join(str(part) for part in error["loc"][1:]) or "body"
            problems.append(f"{field}: {error['msg']}")
    return JSONResponse(status_code=400, content={"detail": problems})
