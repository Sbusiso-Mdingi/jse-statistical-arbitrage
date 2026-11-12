from common import *
dates, ls, ln = load()
m = np.array([t >= dt.date(2024, 4, 1) for t in dates])
for k, r, adv in (("sbk", ls, 647e6), ("ned", ln, 377e6)):
    sig = r[m].std()
    print(k, "daily vol %.2f%%" % (sig * 100))
    for leg in (1e6, 5e6, 10e6, 25e6, 50e6):
        q = leg / adv
        print("   leg R%4.0fm: %.1f%% of daily value; sqrt-impact (Y=0.5..1) %.1f-%.1f bps; if auction is 20%% of value, %.0f%% of auction" % (leg / 1e6, q * 100, 0.5 * sig * math.sqrt(q) * 1e4, sig * math.sqrt(q) * 1e4, q / 0.2 * 100))
