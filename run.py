import asyncio
import platform

if platform.system() == "Windows":
    print("Setting WindowsSelectorEventLoopPolicy")
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

import uvicorn

uvicorn.run("app.core.main:app", host="0.0.0.0", port=8000)
