from fastapi import FastAPI

app = FastAPI(
    name="URL Shortener API",
    version="1.0.0",
    description="A simple URL shortener API built with FastAPI.",
)


@app.get("/")
def read_root():
    return {"message": "Welcome to the URL Shortener API!"}


@app.get("/health")
def health_check():
    return {"status": "healthy"}
