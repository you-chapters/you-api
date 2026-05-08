from fastapi import FastAPI

from app.routers import entries

app = FastAPI()
app.include_router(entries.router)