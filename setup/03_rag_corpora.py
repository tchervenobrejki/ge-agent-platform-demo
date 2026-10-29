# /// script
# requires-python = ">=3.11"
# dependencies = ["google-cloud-aiplatform==1.165.1"]
# ///
"""Step 3: create the two RAG Engine corpora the agent searches.

    uv run setup/03_rag_corpora.py

  - growth-risk-policy-docs  <- data/policies/*.md  (what actions are allowed)
  - growth-risk-support-docs <- data/support/*.md   (runbooks for known problems)

Each corpus uses RAG Engine's managed vector database (RagManagedDb) and the
text-embedding-005 model. Uploading a file chunks it, embeds the chunks and
indexes them; the agent's VertexAiRagRetrieval tool then queries the corpus.

Safe to run more than once: existing corpora and files are reused. Prints the
corpus resource names; setup/05_write_config.sh looks them up the same way.

Cost: new projects run RAG Engine on its Basic tier (Spanner-backed), which is
billed while it exists, even when idle. setup/99_teardown.sh switches it off.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import vertexai
from vertexai import rag

REPO_ROOT = Path(__file__).resolve().parent.parent
PROJECT_ID = os.environ.get("PROJECT_ID") or subprocess.check_output(
    ["gcloud", "config", "get-value", "project"], text=True
).strip()
REGION = os.environ.get("REGION", "europe-west3")
EMBEDDING_MODEL = "publishers/google/models/text-embedding-005"

CORPORA = {
    "growth-risk-policy-docs": (
        "Campaign policy and compliance docs for the growth/risk demo",
        REPO_ROOT / "data/policies",
    ),
    "growth-risk-support-docs": (
        "Support ticket runbooks for the growth/risk demo",
        REPO_ROOT / "data/support",
    ),
}


def find_corpus(display_name: str) -> str | None:
    for corpus in rag.list_corpora():
        if corpus.display_name == display_name:
            return corpus.name
    return None


def main() -> None:
    vertexai.init(project=PROJECT_ID, location=REGION)
    print(f"Project: {PROJECT_ID}, region: {REGION}")

    for display_name, (description, folder) in CORPORA.items():
        name = find_corpus(display_name)
        if name:
            print(f"Reusing corpus {display_name}")
        else:
            print(f"Creating corpus {display_name} ...")
            name = rag.create_corpus(
                display_name=display_name,
                description=description,
                # The vector database defaults to RagManagedDb. Passing
                # rag.RagManagedDb() explicitly crashes in some SDK versions
                # ("Unknown field for RagManagedDb: CopyFrom").
                backend_config=rag.RagVectorDbConfig(
                    rag_embedding_model_config=rag.RagEmbeddingModelConfig(
                        vertex_prediction_endpoint=rag.VertexPredictionEndpoint(
                            publisher_model=EMBEDDING_MODEL
                        )
                    ),
                ),
            ).name

        existing = {f.display_name for f in rag.list_files(name)}
        for path in sorted(folder.glob("*.md")):
            if path.name in existing:
                print(f"  {path.name} already uploaded")
                continue
            print(f"  uploading {path.name} ...")
            rag.upload_file(corpus_name=name, path=str(path), display_name=path.name)

        print(f"  {name}")


if __name__ == "__main__":
    main()
