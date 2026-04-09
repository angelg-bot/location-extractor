"""Shared utilities: token counting, retry, logging."""

import asyncio
import functools
import logging

logger = logging.getLogger("loc_extract")


def count_tokens(text: str, model: str = "cl100k_base") -> int:
    """Estimate token count. Uses tiktoken if available, else rough char/4 estimate."""
    try:
        import tiktoken
        enc = tiktoken.get_encoding(model)
        return len(enc.encode(text))
    except Exception:
        return len(text) // 4


async def retry_async(fn, max_retries=2, backoff=2.0):
    """Retry an async callable with exponential backoff."""
    last_err = None
    for attempt in range(max_retries + 1):
        try:
            return await fn()
        except Exception as e:
            last_err = e
            if attempt < max_retries:
                wait = backoff * (2 ** attempt)
                logger.warning(f"Retry {attempt+1}/{max_retries} after {wait}s: {e}")
                await asyncio.sleep(wait)
    raise last_err
