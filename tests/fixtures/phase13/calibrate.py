"""Temporary calibration script — measures SCALE_FACTOR candidates."""
import string
from rank_bm25 import BM25Okapi
from spacy.lang.en.stop_words import STOP_WORDS

CUSTOM_STOP_WORDS = {"developer", "experience", "engineer", "senior", "junior", "years"}
ALL_STOP_WORDS = STOP_WORDS.union(CUSTOM_STOP_WORDS)

BASE = "tests/fixtures/phase13"

def tokenize(text):
    text = text.lower()
    text = text.translate(str.maketrans("", "", string.punctuation))
    return [t for t in text.split() if t not in ALL_STOP_WORDS]

def load(name):
    return open(f"{BASE}/{name}").read()

jd_medium   = load("jd_medium.txt")
jd_verbose  = load("jd_verbose.txt")
jd_terse    = load("jd_terse.txt")
c_perfect   = load("candidate_perfect.txt")
c_dense     = load("candidate_dense.txt")
c_sparse    = load("candidate_sparse.txt")
c_stuffer   = load("candidate_stuffer.txt")

all_docs    = [c_perfect, c_dense, c_sparse, c_stuffer]
all_labels  = ["perfect", "dense", "sparse", "stuffer"]

print("=" * 70)
print("RAW SCORES PER PAIRING")
print("=" * 70)
for jd_label, jd_text in [("medium", jd_medium), ("verbose", jd_verbose), ("terse", jd_terse)]:
    q_tokens = tokenize(jd_text)
    corp_tokens = [tokenize(d) for d in all_docs]
    bm25 = BM25Okapi(corp_tokens)
    raw = bm25.get_scores(q_tokens).tolist()
    sum_idf = sum(bm25.idf.get(t, 0.0) for t in q_tokens)
    print(f"\nJD={jd_label}  q_tokens={len(q_tokens)}  sum_idf={sum_idf:.4f}")
    for label, r in zip(all_labels, raw):
        print(f"  {label:10s}: raw={r:7.4f}")

print("\n" + "=" * 70)
print("SCALE_FACTOR CALIBRATION (dense vs 3 JDs — band must be < 0.15)")
print("perfect vs jd_medium must land in 0.80-0.85 range")
print("=" * 70)

for sf in [1.2, 1.3, 1.4, 1.5, 1.6]:
    dense_norms = {}
    perfect_vs_medium = None
    stuffer_vs_verbose = None
    dense_vs_verbose = None
    for jd_label, jd_text in [("medium", jd_medium), ("verbose", jd_verbose), ("terse", jd_terse)]:
        q_tokens = tokenize(jd_text)
        corp_tokens = [tokenize(d) for d in all_docs]
        bm25 = BM25Okapi(corp_tokens)
        raw = bm25.get_scores(q_tokens).tolist()
        sum_idf = sum(bm25.idf.get(t, 0.0) for t in q_tokens)
        denom = sum_idf * sf if sum_idf > 0 else 1.0
        norms = [max(0.0, min(r / denom, 1.0)) for r in raw]
        # perfect=0, dense=1, sparse=2, stuffer=3
        dense_norms[jd_label] = norms[1]
        if jd_label == "medium":
            perfect_vs_medium = norms[0]
        if jd_label == "verbose":
            stuffer_vs_verbose = norms[3]
            dense_vs_verbose = norms[1]
    band = max(dense_norms.values()) - min(dense_norms.values())
    dense_beats_stuffer = (dense_vs_verbose > stuffer_vs_verbose) if (dense_vs_verbose and stuffer_vs_verbose) else None
    print(
        f"SF={sf:.1f}  "
        f"dense(med={dense_norms['medium']:.3f} verb={dense_norms['verbose']:.3f} terse={dense_norms['terse']:.3f})  "
        f"band={band:.3f}  "
        f"perfect_vs_medium={perfect_vs_medium:.3f}  "
        f"stuffer_vs_verbose={stuffer_vs_verbose:.3f}  "
        f"dense>stuffer={'YES' if dense_beats_stuffer else 'NO'}"
    )
