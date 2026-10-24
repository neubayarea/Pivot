from fastapi import FastAPI

app = FastAPI(title="Pivot API")


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}
