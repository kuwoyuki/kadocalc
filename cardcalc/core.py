import requests
import ujson
import os
import logging
from pprint import pformat
from .utils.jobs import JobDBCacheSingleton, JobCombatCategory
import re

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
    if call not in ["fights", "events/summary", "events/damage-done", "tables/summary"]:
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
    tethers = [
        {"timestamp": e["timestamp"], "card": e["ability"]}
        for e in event_data["events"]
    ]

    return tethers


def map_comp(comp):
    """
    Maps party composition from summary into a smaller object
    """
    job_name = PASCAL_CASE_PATTERN.sub(" ", comp["type"])
    job = JobDBCacheSingleton.get_job_by_name(job_name)
    return {"id": comp["id"], "guid": comp["guid"], "name": comp["name"], "job": job}


def get_party(report, start, end):
    """
    Makes an fflogs req for summary -> party composition
    """
    options = {"start": start, "end": end}
    res = fflogs_api("tables/summary", report, options)
    return [map_comp(c) for c in res["composition"]]


def get_dmg_events(report, start, end):
    """
    Gets all damage events in a specified timeframe
    """
    options = {"start": start, "end": end}
    events = fflogs_api("events/damage-done", report, options)["events"]

    # TODO: dict with jobs
    lst = [[]]
    start = events[0]["timestamp"]
    for x in events:
        if x["timestamp"] - start <= 1000:
            lst[-1].append(x)
        else:
            lst.append([x])
            start = x["timestamp"]

    return lst


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
        args[0], first_draw["timestamp"], first_draw["timestamp"] + 45000
    )

    f = open("dict.json", "w")
    f.write(ujson.dumps(first_draw_dmg))
    f.close()

    logging.info(pformat(party))
    logging.info(pformat(first_draw))
    logging.info(pformat(first_draw_dmg))
