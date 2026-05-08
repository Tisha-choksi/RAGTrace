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


async def generate_answer(query: str, chunks: list[dict]) -> str:
    provider = settings.ai_provider.lower()
    if provider == "openai" and settings.openai_api_key:
        from openai import AsyncOpenAI

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

    if not chunks:
        return "I could not find relevant document context for that question."

    source_lines = []
    for chunk in chunks[:3]:
        source_lines.append(
            f"- {chunk.get('text', '')[:500]} (source: {chunk.get('filename')}, page {chunk.get('page')})"
        )
    return "Local demo answer based on the most relevant retrieved chunks:\n" + "\n".join(source_lines)
