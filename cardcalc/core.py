import requests
import ujson
import os
import logging
import re
from pprint import pformat
import datetime

from .utils.jobs import JobDBCacheSingleton
from .utils.max_subarray import max_subarray_dmg

# cards = {
#     "1000913": # Balance Drawn, https://www.garlandtools.org/db/#status/913
#     "1000914": # Bole Drawn, https://www.garlandtools.org/db/#status/914
#     "1000915": # Arrow Drawn, https://www.garlandtools.org/db/#status/915
#     "1000916": # Spear Drawn, https://www.garlandtools.org/db/#status/916
#     "1000917": # Ewer Drawn, https://www.garlandtools.org/db/#status/917
#     "1000918": # Spire Drawn, https://www.garlandtools.org/db/#status/918
# }
logging.basicConfig(level="DEBUG")
PASCAL_CASE_PATTERN = re.compile(r"(?<!^)(?=[A-Z])")


def fflogs_fetch(api_url, options):
    """
    Gets a url and handles any API errors
    """
    options["api_key"] = os.environ["FFLOGS_API_KEY"]
    options["translate"] = True
    response = requests.get(api_url, params=options)

    return ujson.loads(response.text)


def fflogs_api(call, report, options={}):
    """
    Makes a call to the FFLogs API and returns a dictionary
    """
    if call not in [
        "fights",
        "events/summary",
        "events/damage-done",
        "tables/summary",
        "tables/damage-done",
    ]:
        return {}

    api_url = "https://www.fflogs.com/v1/report/{}/{}".format(call, report)
    data = fflogs_fetch(api_url, options)

    # If this is a fight list, we're done already
    if call in ["fights", "summary", "events/summary"]:
        return data

    # If this is events, there might be more. Fetch until we have all of it
    while "nextPageTimestamp" in data:
        # Set the new start time
        options["start"] = data["nextPageTimestamp"]
        # Get the extra data
        more_data = fflogs_fetch(api_url, options)
        # Add the new events to the existing data
        data["events"].extend(more_data["events"])

        # Continue the loop if there's more
        if "nextPageTimestamp" in more_data:
            data["nextPageTimestamp"] = more_data["nextPageTimestamp"]
        else:
            del data["nextPageTimestamp"]
            break

    # Return the event data
    return data


def get_draws(report, start, end):
    """
    Gets a list of card draws
    """
    options = {
        "start": start,
        "end": end,
        # cards
        "filter": 'type="applybuff" and (ability.id=1000913 or ability.id=1000914 or ability.id=1000915 or ability.id=1000916 or ability.id=1000917 or id=1000918)',
    }
    event_data = fflogs_api("events/summary", report, options)
    draws = [
        {"timestamp": e["timestamp"], "card": e["ability"]}
        for e in event_data["events"]
    ]

    return draws


def map_comp(comp):
    """
    Maps party composition from summary into a smaller object
    """
    job_name = PASCAL_CASE_PATTERN.sub(" ", comp["type"])
    job = JobDBCacheSingleton.get_job_by_name(job_name)
    pets = comp["pets"] if "pets" in comp else []

    return {
        "id": comp["id"],
        "guid": comp["guid"],
        "name": comp["name"],
        "job": "N/A" if job is None else job[1],
        "pets": [
            {"id": p["id"], "guid": p["guid"], "name": p["name"], "type": p["type"]}
            for p in pets
        ],
    }


def get_party(report, start, end):
    """
    Makes an fflogs req for summary -> party composition
    """
    options = {"start": start, "end": end}
    res = fflogs_api("tables/damage-done", report, options)
    return [map_comp(c) for c in res["entries"]]


def get_dmg_events(report, start, end, party):
    """
    Gets all damage events in a specified timeframe
    """
    options = {"start": start, "end": end}
    events = fflogs_api("events/damage-done", report, options)["events"]

    print(len(events))

    # start = events[0]["timestamp"]
    last = {}

    for x in events:
        src_id = x["sourceID"]
        src_idx = None
        for i, p in enumerate(party):
            if p["id"] == src_id or (
                p["pets"] and any(src_id == y["id"] for y in p["pets"])  # include pets
            ):
                src_idx = i

        # It's an LB or something weird that doesn't belong to a party member
        if src_idx is None:
            continue

        src = party[src_idx]
        if "events" not in src:
            src["events"] = [[]]

        if src_idx in last and x["timestamp"] - last[src_idx] <= 1000:
            src["events"][-1].append(x)
        else:
            src["events"].append([x])
            last[src_idx] = x["timestamp"]

    return party


def calc_dmg(player):
    CARD_DURATION = 15
    best_sum, best_start, best_end = max_subarray_dmg(player["events"], CARD_DURATION)
    start_ts = player["events"][best_start][0]["timestamp"]
    end_ts = player["events"][best_end][0]["timestamp"]

    return {
        "name": player["name"],
        "job": player["job"],
        "total_damage": best_sum,
        "start_timestamp": start_ts,
        "end_timestamp": end_ts,
    }


def convert(ms):
    hours, ms = divmod(ms, 36e5)
    minutes, ms = divmod(ms, 6e4)
    seconds = float(ms) / 1e3
    return "%i:%02i:%06.3f" % (hours, minutes, seconds)


def app():
    """
    Runs the app
    """
    # debug
    args = ["cZGBRqWgfPVKp3yx", 8081809, 8567936]
    party = get_party(*args)
    draws = get_draws(*args)
    # parse draw
    first_draw = draws[0]
    first_draw_dmg = get_dmg_events(
        args[0], first_draw["timestamp"], first_draw["timestamp"] + 45000, party
    )

    f = open("dict.json", "w")
    f.write(ujson.dumps(first_draw_dmg))
    f.close()

    # logging.info(pformat(party))
    # logging.info(pformat(first_draw))
    # logging.info(pformat(first_draw_dmg))

    res = sorted(
        [calc_dmg(x) for x in filter(lambda x: "events" in x, first_draw_dmg)],
        key=lambda x: x["total_damage"],
        reverse=True,
    )
    logging.info(ujson.dumps(res))

    for i, job in enumerate(res):
        # start_ts = first_draw_dmg[job["start_idx"]]
        # end_ts = first_draw_dmg[job["end_idx"]]
        tcs = convert(job["start_timestamp"] - args[1])
        # tce = convert(job["end_timestamp"] - args[2])

        print(
            f'{i+1}. {job["name"]} ({job["job"]}), total dmg: {job["total_damage"]}, card @ {tcs}'
        )
