"""允许 python -m app.temporal.worker 运行。"""
from app.temporal.worker import main
import asyncio

asyncio.run(main())
