/**
 * Find largest subarray of length k
 * Time: O(n)
 * Space: O(1)
 */
export const maxSubarray = (xs: number[], k: number = 15) => {
  if (xs.length < k) return null;

  let bestSum = 0;
  let bestStart = 0;
  let bestEnd = k;
  let currentSum = 0;

  for (let i = 0; i < k; i++) {
    bestSum += xs[i];
  }

  currentSum = bestSum;
  for (let i = k; i < xs.length; i++) {
    currentSum = currentSum - xs[i - k] + xs[i];
    if (currentSum > bestSum) {
      bestSum = currentSum;
      bestStart = i - k + 1;
      bestEnd = i;
    }
  }

  return [bestSum, bestStart, bestEnd];
};
