import { maxSubarray } from "./utils.ts";

/**
 * 1. Get the event summary timeline segment between draws
 * 2. Transform the timeline into an array of seconds (1..30)
 * 3. Sum the pDPS and split by jobs .. [0: {job: "dnc", dps: 123}...]
 * 4. get the maximum subarray of with size 15
 */
