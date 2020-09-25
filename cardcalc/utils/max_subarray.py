def max_subarray(xs, k):
    n = len(xs)
    if n < k:
        return -1

    best_start = 0
    best_end = k
    best_sum = 0
    for i in range(k):
        best_sum += xs[i]

    curr_sum = best_sum
    for i in range(k, n):
        curr_sum += xs[i] - xs[i - k]
        if curr_sum > best_sum:
            best_sum = curr_sum
            best_start = i - k + 1  # actual current sum start idx
            best_end = i + 1  # make it exclusive

    return best_sum, best_start, best_end
