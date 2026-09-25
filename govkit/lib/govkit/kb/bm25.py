"""BM25 sin dependencias (recuperación léxica determinista, sin embeddings ni GPU)."""
from __future__ import annotations

import math
import re
import unicodedata
from collections import Counter
from typing import Dict, List, Tuple

STOP = set("""a al algo como con de del el en es esta este la las lo los mas o para por que se sin su sus un una uno y
ya the of and to in is for on with be are as by an or it this that from at si no ni muy ser son hay debe deben""".split())


def tokenize(text: str) -> List[str]:
    t = "".join(c for c in unicodedata.normalize("NFKD", text.lower()) if not unicodedata.combining(c))
    return [w for w in re.findall(r"[a-z0-9_]{2,}", t) if w not in STOP]


class BM25:
    def __init__(self, docs: Dict[str, str], k1: float = 1.4, b: float = 0.75):
        self.k1, self.b = k1, b
        self.tf = {d: Counter(tokenize(t)) for d, t in docs.items()}
        self.len = {d: sum(c.values()) for d, c in self.tf.items()}
        self.avg = sum(self.len.values()) / max(1, len(self.len))
        df: Counter = Counter()
        for c in self.tf.values():
            df.update(set(c))
        n = len(self.tf)
        self.idf = {w: math.log(1 + (n - f + 0.5) / (f + 0.5)) for w, f in df.items()}

    def search(self, query: str, k: int = 5) -> List[Tuple[str, float]]:
        q = tokenize(query)
        scores = {}
        for d, c in self.tf.items():
            s = 0.0
            for w in q:
                if w in c:
                    f = c[w]
                    s += self.idf[w] * f * (self.k1 + 1) / (f + self.k1 * (1 - self.b + self.b * self.len[d] / self.avg))
            if s > 0:
                scores[d] = s
        return sorted(scores.items(), key=lambda x: -x[1])[:k]
