import json
import urllib.request

import litellm

from app.core.config import settings
from app.core.exceptions import (
    EmbeddingDimensionMismatchException,
    EmbeddingGenerationException,
)
from app.core.logging import log_action, logger

_sentence_model = None


def _get_sentence_transformer():
    global _sentence_model
    if _sentence_model is None:
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError:
            raise ImportError(
                "sentence-transformers is not installed. "
                "It is excluded from requirements.txt to keep the Vercel deployment "
                "within the 250 MB bundle limit. Install it locally with: "
                "pip install sentence-transformers>=2.7.0"
            )
        fallback_name = (
            settings.EMBEDDING_MODEL
            if not settings.EMBEDDING_MODEL.startswith(("gemini", "groq", "jina", "text-embedding", "models/"))
            else "sentence-transformers/all-MiniLM-L6-v2"
        )
        logger.info(f"Initializing local embedding model: {fallback_name}")
        _sentence_model = SentenceTransformer(fallback_name)
    return _sentence_model



def _call_jina_api(texts: list[str], task_type: str = "retrieval.query") -> list[list[float]]:
    """Calls Jina AI Embeddings API (v3/v5) with 768 dimensions constraint."""
    api_key = getattr(settings, "EMBEDDING_API_KEY", "") or settings.LLM_API_KEY
    if not api_key or not api_key.startswith("jina_"):
        return []

    url = "https://api.jina.ai/v1/embeddings"
    payload = {
        "model": settings.EMBEDDING_MODEL if "jina" in settings.EMBEDDING_MODEL else "jina-embeddings-v5-omni-small",
        "task": task_type,
        "dimensions": settings.EMBEDDING_DIMENSION,
        "normalized": True,
        "input": texts
    }

    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
            "User-Agent": "Mozilla/5.0"
        }
    )

    with urllib.request.urlopen(req, timeout=15.0) as resp:
        data = json.loads(resp.read().decode("utf-8"))
        embeddings = [item["embedding"] for item in data.get("data", [])]
        return embeddings


def generate_embedding(text: str) -> list[float]:
    """
    Generates embedding vector for input text supporting Jina AI, Gemini,
    Groq, and local SentenceTransformer models with dimension validation.
    Explicitly requests output_dimensionality matching settings.EMBEDDING_DIMENSION (768).

    Raises EmbeddingGenerationException if every real provider fails, instead of
    silently returning a SHA256-hash-derived vector. A hash-based vector has zero
    semantic meaning: cosine similarity against it produces plausible-looking but
    meaningless scores with no error surfaced anywhere, which is a correctness bug
    for a RAG system whose whole premise is grounded, citable retrieval.
    """
    if not text or not text.strip():
        text = "empty"

    vector = None
    model_name = settings.EMBEDDING_MODEL
    errors: list[str] = []

    if "jina" in model_name or (hasattr(settings, "EMBEDDING_API_KEY") and settings.EMBEDDING_API_KEY.startswith("jina_")):
        try:
            results = _call_jina_api([text], task_type="retrieval.query")
            if results:
                vector = results[0]
        except Exception as e:
            logger.warning(f"Jina AI embedding API call failed: {e}. Trying secondary provider.")
            errors.append(f"jina: {e}")

    if vector is None and model_name.startswith(("gemini", "groq", "text-embedding", "models/")):
        try:
            response = litellm.embedding(
                model=model_name,
                input=[text],
                dimensions=settings.EMBEDDING_DIMENSION,
                api_key=settings.LLM_API_KEY,
                timeout=10.0
            )
            raw = response.data[0]["embedding"]
            if len(raw) == settings.EMBEDDING_DIMENSION:
                vector = raw
            else:
                multiplier = (settings.EMBEDDING_DIMENSION // len(raw)) + 1
                vector = (raw * multiplier)[:settings.EMBEDDING_DIMENSION]
        except Exception as e:
            logger.warning(f"Cloud embedding API call ({model_name}) failed: {e}. Falling back to local model.")
            errors.append(f"cloud[{model_name}]: {e}")

    if vector is None:
        try:
            st_model = _get_sentence_transformer()
            raw = st_model.encode(text, convert_to_numpy=True).tolist()
            if len(raw) == settings.EMBEDDING_DIMENSION:
                vector = raw
            else:
                multiplier = (settings.EMBEDDING_DIMENSION // len(raw)) + 1
                vector = (raw * multiplier)[:settings.EMBEDDING_DIMENSION]
        except Exception as e:
            logger.error(f"SentenceTransformer fallback error: {e}. No embedding provider succeeded.")
            errors.append(f"local_sentence_transformer: {e}")

    if vector is None:
        raise EmbeddingGenerationException(
            "All embedding providers failed (Jina, cloud LiteLLM, local SentenceTransformer). "
            "Refusing to generate a fake placeholder vector.",
            details={"errors": errors, "text_preview": text[:80]}
        )

    if len(vector) != settings.EMBEDDING_DIMENSION:
        raise EmbeddingDimensionMismatchException(
            f"Generated vector dimension ({len(vector)}) does not match configured EMBEDDING_DIMENSION ({settings.EMBEDDING_DIMENSION})."
        )

    return vector


def generate_embeddings_batch(texts: list[str]) -> list[list[float]]:
    """
    Generates embedding vectors for a batch of text chunks with explicit
    dimensions=settings.EMBEDDING_DIMENSION constraint.

    Raises EmbeddingGenerationException if every real provider fails, instead of
    silently returning SHA256-hash-derived placeholder vectors for the whole batch.
    """
    if not texts:
        return []

    vectors = []
    model_name = settings.EMBEDDING_MODEL
    errors: list[str] = []

    if "jina" in model_name or (hasattr(settings, "EMBEDDING_API_KEY") and settings.EMBEDDING_API_KEY.startswith("jina_")):
        try:
            vectors = _call_jina_api(texts, task_type="retrieval.passage")
        except Exception as e:
            logger.warning(f"Batch Jina AI embedding failed: {e}. Trying secondary provider.")
            errors.append(f"jina: {e}")
            vectors = []

    if not vectors and model_name.startswith(("gemini", "groq", "text-embedding", "models/")):
        try:
            response = litellm.embedding(
                model=model_name,
                input=texts,
                dimensions=settings.EMBEDDING_DIMENSION,
                api_key=settings.LLM_API_KEY,
                timeout=15.0
            )
            for item in response.data:
                raw = item["embedding"]
                if len(raw) == settings.EMBEDDING_DIMENSION:
                    vectors.append(raw)
                else:
                    multiplier = (settings.EMBEDDING_DIMENSION // len(raw)) + 1
                    vectors.append((raw * multiplier)[:settings.EMBEDDING_DIMENSION])
        except Exception as e:
            logger.warning(f"Batch cloud embedding failed: {e}. Falling back to local batch generation.")
            errors.append(f"cloud[{model_name}]: {e}")
            vectors = []

    if not vectors:
        try:
            st_model = _get_sentence_transformer()
            raw_batch = st_model.encode(texts, convert_to_numpy=True).tolist()
            for raw in raw_batch:
                if len(raw) == settings.EMBEDDING_DIMENSION:
                    vectors.append(raw)
                else:
                    multiplier = (settings.EMBEDDING_DIMENSION // len(raw)) + 1
                    vectors.append((raw * multiplier)[:settings.EMBEDDING_DIMENSION])
        except Exception as e:
            logger.error(f"Batch SentenceTransformer fallback error: {e}. No embedding provider succeeded.")
            errors.append(f"local_sentence_transformer: {e}")

    if not vectors:
        raise EmbeddingGenerationException(
            "All embedding providers failed for this batch (Jina, cloud LiteLLM, local SentenceTransformer). "
            "Refusing to generate fake placeholder vectors.",
            details={"errors": errors, "batch_size": len(texts)}
        )

    for idx, vec in enumerate(vectors):
        if len(vec) != settings.EMBEDDING_DIMENSION:
            raise EmbeddingDimensionMismatchException(
                f"Vector at index {idx} dimension ({len(vec)}) does not match expected ({settings.EMBEDDING_DIMENSION})."
            )

    log_action(
        "EMBEDDING_CREATED",
        status="SUCCESS",
        details={"batch_size": len(texts), "dimension": settings.EMBEDDING_DIMENSION, "model": model_name}
    )

    return vectors
