"""Allow running as: python -m src"""

from .main import main
import asyncio

asyncio.run(main())
