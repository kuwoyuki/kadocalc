def sum_dmg(xs):
    return sum(x["amount"] for x in xs)


def max_subarray_dmg(xs, k):
    n = len(xs)
    if n < k:
        k = n

    best_start = 0
    best_end = k
    best_sum = 0
    for i in range(k):
        best_sum += sum_dmg(xs[i])

    curr_sum = best_sum
    for i in range(k, n):
        curr_sum += sum_dmg(xs[i]) - sum_dmg(xs[i - k])
        if curr_sum > best_sum:
            best_sum = curr_sum
            best_start = i - k + 1  # actual current sum start idx
            best_end = i + 1  # make it exclusive

    return best_sum, best_start, best_end
