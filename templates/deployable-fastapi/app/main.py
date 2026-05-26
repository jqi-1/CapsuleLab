from fastapi import FastAPI
from fastapi.responses import JSONResponse

app = FastAPI(title="Model API", version="0.1.0")


@app.get("/health")
def health():
    return {"status": "healthy"}


@app.get("/")
def root():
    return {"message": "Model API is running", "docs": "/docs"}
