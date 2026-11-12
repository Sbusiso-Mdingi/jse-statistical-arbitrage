import sys; sys.path.insert(0, "/tmp/jse-review/design")
from core import *
import pickle
w = wstats(x, y)
pickle.dump(w, open("/tmp/jse-review/design/w126.pkl", "wb"))
gate = w["eg"] < -2.8
ref = sw.trades((gate & dev).astype(np.int8), np.full(n, 0.5), w["b"], w["z"], copula_on=False, hold_through=True)
line("engine (frozen H16)", ref)
mine = sim(w["z"], w["b"], gate)
line("scratch sim", mine)
print("identical trades:", [(a["open"], a["close"]) for a in ref] == [(a["open"], a["close"]) for a in mine], len(ref), len(mine))
