def convert(ms):
    minutes, ms = divmod(ms, 6e4)
    seconds = float(ms) / 1e3
    return "%02i:%06.3f" % (minutes, seconds)
