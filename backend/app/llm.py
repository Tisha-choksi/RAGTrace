import asyncio
from typing import AsyncGenerator

try:
    from openai import AsyncOpenAI
except ImportError:
    AsyncOpenAI = None  # type: ignore[assignment,misc]

from app.config import settings


def active_model_name() -> str:
    provider = settings.ai_provider.lower()
    if provider == "openai" and settings.openai_api_key:
        return settings.openai_model
    if provider == "gemini" and settings.gemini_api_key:
        return settings.gemini_model
    return "local-extractive-demo"


def build_prompt(query: str, chunks: list[dict]) -> str:
    context = "\n\n".join(
        f"Source {idx + 1} ({chunk.get('filename')}, page {chunk.get('page')}): {chunk.get('text')}"
        for idx, chunk in enumerate(chunks)
    )
    return (
        "Answer the user's question using only the provided sources. "
        "If the answer is not supported by the sources, say so.\n\n"
        f"Question: {query}\n\nSources:\n{context}"
    )


def _local_demo_answer(chunks: list[dict]) -> str:
    if not chunks:
        return "I could not find relevant document context for that question."
    source_lines = [
        f"- {chunk.get('text', '')[:500]} (source: {chunk.get('filename')}, page {chunk.get('page')})"
        for chunk in chunks[:3]
    ]
    return "Local demo answer based on the most relevant retrieved chunks:\n" + "\n".join(source_lines)


async def generate_answer(query: str, chunks: list[dict]) -> str:
    provider = settings.ai_provider.lower()
    if provider == "openai" and settings.openai_api_key and AsyncOpenAI is not None:
        client = AsyncOpenAI(api_key=settings.openai_api_key)
        response = await client.chat.completions.create(
            model=settings.openai_model,
            messages=[{"role": "user", "content": build_prompt(query, chunks)}],
            temperature=0.2,
        )
        return response.choices[0].message.content or ""

    if provider == "gemini" and settings.gemini_api_key:
        import google.generativeai as genai

        genai.configure(api_key=settings.gemini_api_key)
        model = genai.GenerativeModel(settings.gemini_model)
        response = await model.generate_content_async(build_prompt(query, chunks))
        return response.text or ""

    return _local_demo_answer(chunks)


async def generate_answer_stream(query: str, chunks: list[dict]) -> AsyncGenerator[str, None]:
    provider = settings.ai_provider.lower()

    if provider == "openai" and settings.openai_api_key and AsyncOpenAI is not None:
        client = AsyncOpenAI(api_key=settings.openai_api_key)
        stream = await client.chat.completions.create(
            model=settings.openai_model,
            messages=[{"role": "user", "content": build_prompt(query, chunks)}],
            temperature=0.2,
            stream=True,
        )
        async for chunk in stream:
            token = chunk.choices[0].delta.content or ""
            if token:
                yield token
        return

    if provider == "gemini" and settings.gemini_api_key:
        import google.generativeai as genai

        genai.configure(api_key=settings.gemini_api_key)
        model = genai.GenerativeModel(settings.gemini_model)
        async for chunk in model.generate_content_async(build_prompt(query, chunks), stream=True):
            token = chunk.text or ""
            if token:
                yield token
        return

    # Local demo: simulate streaming word-by-word
    for word in _local_demo_answer(chunks).split(" "):
        yield word + " "
        await asyncio.sleep(0.04)
