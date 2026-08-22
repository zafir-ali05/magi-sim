from fastapi import FastAPI
from fastapi.responses import StreamingResponse

from .deliberation import deliberate
from .models import Motion

app = FastAPI()


@app.post("/api/discuss")
async def discuss(motion: Motion) -> StreamingResponse:
    async def body():
        async for event in deliberate(motion):
            yield event.model_dump_json() + "\n"

    return StreamingResponse(body(), media_type="application/x-ndjson")
