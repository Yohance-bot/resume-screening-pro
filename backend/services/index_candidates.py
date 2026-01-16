# scripts/index_candidates.py

from app import app, db
from models import Candidate
from services.embeddings import EmbeddingGenerator
from services.vector_db import VectorDatabase


def index_all_candidates():
    embedder = EmbeddingGenerator()
    vector_db = VectorDatabase()
    collection = vector_db.collection

    candidates = Candidate.query.all()
    print(f"Indexing {len(candidates)} candidates into Chroma...")

    ids = []
    embeddings = []
    metadatas = []

    for cand in candidates:
        # Build rich searchable text from candidate fields
        text = embedder.build_candidate_text(cand)
        if not text or not text.strip():
            continue

        embedding = embedder.generate_embedding(text)

        ids.append(str(cand.id))  # Chroma document ID
        embeddings.append(embedding)
        metadatas.append({
            "id": cand.id,  # integer PK for SQL lookup
            "full_name": cand.full_name,
            "email": cand.email,
            "primary_role": cand.primary_role,
            "primary_domain": cand.primary_domain,
        })

    if ids:
        collection.add(
            ids=ids,
            embeddings=embeddings,
            metadatas=metadatas,
        )

    print("Done indexing candidates.")


if __name__ == "__main__":
    with app.app_context():
        index_all_candidates()
