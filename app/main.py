from fastapi import FastAPI

from app.routers import entries, phases

app = FastAPI()
app.include_router(entries.router)
app.include_router(phases.router)