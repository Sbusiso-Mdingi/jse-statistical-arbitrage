"""H21 (research/PROTOCOL.md): H16's rule, unchanged, on the four Big Four bank cross-pairs. Run once, as registered.

  python research/h21_big_four.py [path to jse-risk-management]     # use that repo's venv

Same engine, data and execution as H20 (research/h20_other_pairs.py). Writes research/results/h21.json.
"""
import sys
sys.path.insert(0, "research")
import h20_other_pairs as h20  # noqa: E402

PAIRS = [("Banks", "SBK", "FSR"), ("Banks", "SBK", "ABG"), ("Banks", "NED", "FSR"), ("Banks", "NED", "ABG")]

if __name__ == "__main__":
    h20.main(PAIRS, "research/results/h21.json", "H21")
