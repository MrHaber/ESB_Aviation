
import asyncio
import platform
from asyncio import WindowsSelectorEventLoopPolicy

def fix_windows_event_loop():
    if platform.system() == "Windows":
        asyncio.set_event_loop_policy(WindowsSelectorEventLoopPolicy())
