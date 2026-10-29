"""Support-ticket and policy search over Vertex AI RAG Engine.

Queries the two RagCorpus resources setup/03_rag_corpora.py creates
(POLICY_RAG_CORPUS, SUPPORT_RAG_CORPUS).

Explicit function tools, not the built-in VertexAiRagRetrieval used until the
agents-cli 1.10 rebuild: with the built-in, Gemini decides whether to retrieve
at all, and the first baseline eval showed the RAG agents inventing tickets,
runbooks and policy sections that are not in either corpus -- with nothing in
the trace to show whether retrieval happened. Here every search is a visible
function call whose response carries the exact chunks, so the agents can cite
them and the hallucination metric can check claims against them.

Corpus resource names come from env vars, read at call time. An empty corpus
name returns an error rather than fake data.
"""

from __future__ import annotations

import functools
import os
from typing import Any

from google.api_core import exceptions as api_exceptions
from google.auth.transport import mtls
from google.cloud import aiplatform_v1

_TOP_K = 4


@functools.cache
def _client(host: str) -> aiplatform_v1.VertexRagServiceClient:
    return aiplatform_v1.VertexRagServiceClient(client_options={"api_endpoint": host})


# Region -> host that last answered without a 401.
_WORKING_HOST: dict[str, str] = {}


def _hosts(region: str) -> list[str]:
    """Regional hosts to try, preferred first.

    Regional client instead of vertexai.init(), which would change the
    process-wide default location for every other Vertex AI caller. Under
    Agent Identity the runtime presents a client certificate and its tokens
    are bound to it, so calls must go to the mTLS host; an explicit
    api_endpoint bypasses the library's own mTLS endpoint selection (the first
    live deploy got 401s from the plain host). google-auth's public helper
    picks the preferred host, and the other is kept as a fallback on 401.
    """
    plain = f"{region}-aiplatform.googleapis.com"
    mtls_host = f"{region}-aiplatform.mtls.googleapis.com"
    preferred = [mtls_host, plain] if mtls.should_use_mtls_endpoint() else [plain, mtls_host]
    if working := _WORKING_HOST.get(region):
        preferred.remove(working)
        preferred.insert(0, working)
    return preferred


def _search(corpus_env: str, query: str) -> dict[str, Any]:
    corpus = os.environ.get(corpus_env, "")
    parts = corpus.split("/")
    if len(parts) < 6 or parts[2] != "locations":
        return {"status": "error", "error_message": f"{corpus_env} is not configured."}
    request = {
        "parent": "/".join(parts[:4]),
        "vertex_rag_store": {"rag_resources": [{"rag_corpus": corpus}]},
        "query": {"text": query, "rag_retrieval_config": {"top_k": _TOP_K}},
    }
    region = parts[3]
    response = None
    last_error = None
    for host in _hosts(region):
        try:
            response = _client(host).retrieve_contexts(request=request)
        except api_exceptions.Unauthenticated as exc:
            last_error = exc  # wrong host for this credential; try the other
            continue
        except Exception as exc:
            return {"status": "error", "error_message": str(exc)}
        _WORKING_HOST[region] = host
        break
    if response is None:
        return {"status": "error", "error_message": str(last_error)}
    chunks = [
        {"source": c.source_display_name or c.source_uri, "text": c.text}
        for c in response.contexts.contexts
    ]
    if not chunks:
        return {"status": "success", "chunks": [], "note": "No matching documents."}
    return {"status": "success", "chunks": chunks}


def search_support_docs(query: str) -> dict[str, Any]:
    """Search support tickets and runbooks for customer feedback.

    Use when investigating post-campaign user complaints, checkout issues, or
    conversion drop reports from customer support channels.

    Args:
        query: What to look for, e.g. "checkout timeout complaints 2025-06-26".

    Returns:
        dict with status and chunks (each with source and verbatim text). Only
        these chunks are evidence; nothing else may be cited as a ticket or
        runbook.
    """
    return _search("SUPPORT_RAG_CORPUS", query)


def search_policy_docs(query: str) -> dict[str, Any]:
    """Search marketing and compliance policy documents.

    Use before recommending campaign pauses, budget changes, or discount
    actions. Policies define approval thresholds and rollback procedures.

    Args:
        query: What to look for, e.g. "campaign pause approval rules".

    Returns:
        dict with status and chunks (each with source and verbatim text). Only
        these chunks are evidence; nothing else may be quoted as policy.
    """
    return _search("POLICY_RAG_CORPUS", query)
