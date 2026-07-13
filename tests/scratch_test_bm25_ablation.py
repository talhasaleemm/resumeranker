import sys
from pathlib import Path
sys.path.insert(0, str(Path.cwd()))
from app.services.matching.bm25_engine import compute_normalized_bm25_scores, _tokenize
import app.services.matching.bm25_engine as bm25_engine

# Disable standard stopword filtering temporarily
original_stop_words = bm25_engine.ALL_STOP_WORDS
bm25_engine.ALL_STOP_WORDS = bm25_engine.CUSTOM_STOP_WORDS # Only custom

query = "looking for a backend python programmer"
docs = [
    "looking for a frontend react programmer",
    "looking for a backend python programmer",
    "a completely unrelated document",
    "another unrelated document",
    "yet another unrelated document"
]
print("--- Old test, NO filtering ---")
scores = compute_normalized_bm25_scores(query, docs)
print(f"Doc 1: {scores[0]}, Doc 2: {scores[1]}")
print(f"Passes? {scores[1] > scores[0]}")

print("\n--- New test idea, NO filtering ---")
query2 = "looking for a backend python programmer"
docs2 = [
    "looking for a looking for a looking for a looking for a frontend programmer",
    "backend python",
    "a completely unrelated document",
    "another unrelated document",
    "yet another unrelated document"
]
scores2 = compute_normalized_bm25_scores(query2, docs2)
print(f"Doc 1: {scores2[0]}, Doc 2: {scores2[1]}")
print(f"Passes? {scores2[1] > scores2[0]}")

# Re-enable filtering
bm25_engine.ALL_STOP_WORDS = original_stop_words

print("\n--- New test idea, WITH filtering ---")
scores3 = compute_normalized_bm25_scores(query2, docs2)
print(f"Doc 1: {scores3[0]}, Doc 2: {scores3[1]}")
print(f"Passes? {scores3[1] > scores3[0]}")
