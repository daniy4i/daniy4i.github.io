import time

from fastapi import FastAPI
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.api.routes import router
from app.core.logging import configure_logging
from app.db.session import Base, engine

configure_logging()

app = FastAPI(title="NYC Traffic Intelligence")
app.include_router(router)


@app.on_event("startup")
def startup_init_db() -> None:
    max_attempts = 30
    delay_seconds = 2

    for attempt in range(1, max_attempts + 1):
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            Base.metadata.create_all(bind=engine)
            return
        except SQLAlchemyError:
            if attempt == max_attempts:
                raise
            time.sleep(delay_seconds)


@app.get("/health")
def health():
    return {"ok": True}
