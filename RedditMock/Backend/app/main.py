from fastapi import FastAPI

from app.routes import router

app = FastAPI(

    title="Reddit RSS POC",

    version="1.0"

)

app.include_router(router)