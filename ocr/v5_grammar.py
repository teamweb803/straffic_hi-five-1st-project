"""
Grammar Beam Decoder:
  - 한국 번호판 패턴: NN한글NNNN  또는  NNN한글NNNN  (총 7자/8자)
  - beam search (width=10)
  - invalid 출력 억제
"""
import math
import re
import numpy as np
import torch

PAT_7 = re.compile(r"^\d{2}[가-힣]\d{4}$")
PAT_8 = re.compile(r"^\d{3}[가-힣]\d{4}$")


def is_valid_kr_plate(s):
    return bool(PAT_7.match(s) or PAT_8.match(s))


def beam_search_decode(log_probs, idx2char, beam_width=10, blank=0):
    """
    log_probs: (T, V) numpy or tensor (single sample, log scale)
    Returns: list of (sequence, score) sorted by score desc
    """
    if isinstance(log_probs, torch.Tensor):
        log_probs = log_probs.detach().cpu().numpy()
    T, V = log_probs.shape

    # state: (prefix_str, last_char_idx_or_None)
    # beam: list of (str, last_idx, log_score_blank, log_score_nblank)
    NEG_INF = -1e30
    beams = {("", -1): (0.0, NEG_INF)}    # (Pb, Pnb) at t=0 before processing first frame

    for t in range(T):
        new_beams = {}
        lp = log_probs[t]
        for (prefix, last), (Pb, Pnb) in beams.items():
            for v in range(V):
                p = lp[v]
                if v == blank:
                    nb = (prefix, last)
                    nb_pb, nb_pnb = new_beams.get(nb, (NEG_INF, NEG_INF))
                    nb_pb = np.logaddexp(nb_pb, np.logaddexp(Pb, Pnb) + p)
                    new_beams[nb] = (nb_pb, nb_pnb)
                else:
                    ch = idx2char.get(v, "")
                    if v == last:
                        # repeat without blank → stays as same prefix; with blank → extend
                        # via Pnb path: same prefix, repeat → adds to Pnb
                        nb = (prefix, last)
                        nb_pb, nb_pnb = new_beams.get(nb, (NEG_INF, NEG_INF))
                        nb_pnb = np.logaddexp(nb_pnb, Pnb + p)
                        new_beams[nb] = (nb_pb, nb_pnb)
                        # via Pb: extend
                        new_prefix = prefix + ch
                        nb2 = (new_prefix, v)
                        nb2_pb, nb2_pnb = new_beams.get(nb2, (NEG_INF, NEG_INF))
                        nb2_pnb = np.logaddexp(nb2_pnb, Pb + p)
                        new_beams[nb2] = (nb2_pb, nb2_pnb)
                    else:
                        new_prefix = prefix + ch
                        nb = (new_prefix, v)
                        nb_pb, nb_pnb = new_beams.get(nb, (NEG_INF, NEG_INF))
                        nb_pnb = np.logaddexp(nb_pnb, np.logaddexp(Pb, Pnb) + p)
                        new_beams[nb] = (nb_pb, nb_pnb)
        # prune to beam_width
        scored = [
            (k, v, np.logaddexp(v[0], v[1])) for k, v in new_beams.items()
        ]
        scored.sort(key=lambda x: x[2], reverse=True)
        scored = scored[:beam_width]
        beams = {k: v for k, v, _ in scored}

    finals = [(k[0], np.logaddexp(v[0], v[1])) for k, v in beams.items()]
    finals.sort(key=lambda x: x[1], reverse=True)
    return finals


def grammar_decode(log_probs, idx2char, beam_width=10):
    """beam search → 패턴 통과 첫 후보 반환. 모두 fail 시 top-1 반환."""
    cands = beam_search_decode(log_probs, idx2char, beam_width=beam_width)
    for s, _ in cands:
        if is_valid_kr_plate(s):
            return s, True
    return (cands[0][0] if cands else ""), False


def grammar_decode_batch(log_probs_BTV, idx2char, beam_width=10):
    """log_probs (B,T,V) → list[(text, valid)]"""
    if isinstance(log_probs_BTV, torch.Tensor):
        log_probs_BTV = log_probs_BTV.detach().cpu().numpy()
    out = []
    for b in range(log_probs_BTV.shape[0]):
        out.append(grammar_decode(log_probs_BTV[b], idx2char, beam_width))
    return out
