"""Module E data: radio log, phrase patterns, two reports (plus trap 49)."""
from common import ALPHABET, LETTERS_DIGITS

PATTERN_LENGTHS = [2, 4, 8, 12, 20, 40]


def count_overlapping(text, pat):
    c, i = 0, text.find(pat)
    while i != -1:
        c += 1
        i = text.find(pat, i + 1)
    return c


def edit_distance(a, b):
    """Levenshtein distance (Wagner-Fischer, two rows)."""
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i] + [0] * len(b)
        for j, cb in enumerate(b, 1):
            cur[j] = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb))
        prev = cur
    return prev[-1]


def _word(rng, sub, n):
    return "".join(rng.choice(sub) for _ in range(n))


def _log_normal(case, rng, L):
    scen = case.scenario
    sub = ALPHABET if scen == 3 else "".join(rng.sample(LETTERS_DIGITS, rng.randint(14, 26)))
    vocab = [_word(rng, sub, rng.randint(2, 7)) for _ in range(rng.randint(8, 30))]
    weights = [1 / (i + 1) ** 1.1 for i in range(len(vocab))]
    if scen == 6:                      # beacons repeat the same message
        weights[0] *= 6
    pieces, total = [], 0
    while total < L:
        msg = "_".join(rng.choices(vocab, weights, k=rng.randint(1, 4)))
        if scen == 3:                  # radio full of noise
            msg = "".join(rng.choice(ALPHABET) if rng.random() < 0.3 else ch for ch in msg)
        sep = "-" * rng.randint(3, 9) if scen == 6 else rng.choice("-_")
        pieces.append(msg + sep)
        total += len(msg) + len(sep)
    return "".join(pieces)[:L], sub


def _patterns(rng, log):
    present = [True, True, True] + [rng.random() < 0.5 for _ in range(3)]
    if all(present):
        present[5] = False
    pats = []
    for m, pr in zip(PATTERN_LENGTHS, present):
        if pr:
            i = rng.randint(0, len(log) - m)
            pats.append(log[i:i + m])
            continue
        for _ in range(500):                       # a near-miss copy that never occurs
            i = rng.randint(0, len(log) - m)
            p = list(log[i:i + m])
            j = m - 1 if rng.random() < 0.5 else rng.randrange(m)
            p[j] = rng.choice([c for c in ALPHABET if c != p[j]])
            p = "".join(p)
            if log.find(p) == -1:
                pats.append(p)
                break
        else:
            return None
    return pats


def _trap49(rng, L):
    """Near-miss trap: ~93% of the log is one symbol Q repeated; every pattern is
    Q^(m-1) followed by another symbol, so its first m-1 symbols match almost
    everywhere but the full pattern occurs at most once."""
    Q = rng.choice(LETTERS_DIGITS)
    others = [c for c in ALPHABET if c != Q]
    picks = rng.sample(others, 6)
    z1, z2, absent = picks[0], picks[1], picks[2:]
    noise_alpha = [c for c in others if c not in absent]
    n1 = round(L * rng.uniform(0.02, 0.035))
    n2 = round(L * rng.uniform(0.02, 0.035))
    q_total = L - n1 - n2
    r1 = round(q_total * rng.uniform(0.3, 0.45))
    r2 = round(q_total * rng.uniform(0.25, 0.35))
    r3 = q_total - r1 - r2
    N1 = z1 + "".join(rng.choice(noise_alpha) for _ in range(n1 - 1))
    N2 = z2 + "".join(rng.choice(noise_alpha) for _ in range(n2 - 1))
    log = Q * r1 + N1 + Q * r2 + N2 + Q * r3
    pats = [Q * (m - 1) + c for m, c in zip(PATTERN_LENGTHS, [z1, z2] + absent)]
    return log, pats


def _split(rng, log):
    parts, i = [], 0
    while i < len(log):
        size = rng.randint(4000, 10000)
        parts.append(log[i:i + size])
        i += size
    return parts


def _reports(case, rng, sub):
    lo, hi = case.gen_range("report")
    alpha = sub + "_"
    while True:
        la = rng.randint(lo, hi)
        a = _word(rng, alpha, la)
        b = list(a)
        for _ in range(max(1, round(la * rng.uniform(0.08, 0.3)))):
            r = rng.random()
            if r < 0.4 and b:
                b[rng.randrange(len(b))] = rng.choice(ALPHABET)
            elif r < 0.7:
                b.insert(rng.randint(0, len(b)), rng.choice(ALPHABET))
            elif b:
                del b[rng.randrange(len(b))]
        b = "".join(b)
        if lo <= len(b) <= hi and a != b:
            return a, b


def generate(case):
    for attempt in range(500):
        rng = case.rng("radio", attempt)
        L = case.size("log", rng)
        if case.k == 49:
            log, pats = _trap49(rng, L)
            sub = LETTERS_DIGITS
        else:
            log, sub = _log_normal(case, rng, L)
            if case.scenario == 3 and len(set(log)) < 32:
                continue
            if case.scenario == 6 and 100 * max(log.count(c) for c in set(log)) < 28 * L:
                continue
            pats = _patterns(rng, log)
            if pats is None:
                continue
        counts = [count_overlapping(log, p) for p in pats]
        if sum(c > 0 for c in counts) < 2 or all(c > 0 for c in counts):
            continue
        parts = _split(rng, log)
        a, b = _reports(case, rng, sub)
        return dict(log=log, parts=parts, patterns=list(zip(pats, counts)),
                    report=(a, b), edit_bound=edit_distance(a, b))
    raise RuntimeError(f"radio: no valid instance for case {case.case_id}")
