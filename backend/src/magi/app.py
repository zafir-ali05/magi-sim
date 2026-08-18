from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from .deliberation import deliberate
from .models import Motion


app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/api/discuss")
async def discuss(motion: Motion) -> StreamingResponse:
    async def body():
        async for event in deliberate(motion):
            yield event.model_dump_json() + "\n"

    return StreamingResponse(body(), media_type="application/x-ndjson")
