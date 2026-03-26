"""Allow running the package directly: python -m src.main"""

import asyncio

from .main import main

asyncio.run(main())
