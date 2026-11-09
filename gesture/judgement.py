def judge(delta):
    error = abs(delta)
    if error <= 0.1 + 1e-9:
        return "PERFECT"
    if error <= 0.2 + 1e-9:
        return "GOOD"
    return "MISS"
