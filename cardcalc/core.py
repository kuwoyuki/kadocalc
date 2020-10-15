import click
import requests
import ujson
import os
import re
import copy

from .utils.jobs import JobDBCacheSingleton
from .utils.max_subarray import max_subarray_dmg
from .utils.time import convert

# cards = {
#     "1000913": # Balance Drawn, https://www.garlandtools.org/db/#status/913
#     "1000914": # Bole Drawn, https://www.garlandtools.org/db/#status/914
#     "1000915": # Arrow Drawn, https://www.garlandtools.org/db/#status/915
#     "1000916": # Spear Drawn, https://www.garlandtools.org/db/#status/916
#     "1000917": # Ewer Drawn, https://www.garlandtools.org/db/#status/917
#     "1000918": # Spire Drawn, https://www.garlandtools.org/db/#status/918
# }
# logging.basicConfig(level="DEBUG")
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

    try:
        start_ts = next(iter(player["events"][best_start]), None)
        start_ts = None if start_ts is None else start_ts["timestamp"]
    except IndexError:
        start_ts = None

    return {
        "name": player["name"],
        "job": player["job"],
        "total_damage": best_sum,
        "start_timestamp": start_ts,
    }


def get_fight_times(report, fight_id):
    """
    Gets fight start and end by id
    """
    res = fflogs_api("fights", report)
    fight = next((fight for fight in res["fights"] if fight["id"] == fight_id), None)
    return fight["start_time"], fight["end_time"]


@click.command()
@click.option(
    "--report", required=True, prompt="FFLogs report ID", help="Number of greetings."
)
@click.option(
    "--fight",
    required=True,
    prompt="FFLogs report fight ID",
    type=int,
    help="The person to greet.",
)
def app(report, fight):
    """
    Runs the app
    """
    fight_start, fight_end = get_fight_times(report, fight)
    args = [report, fight_start, fight_end]
    party = get_party(*args)
    draws = get_draws(*args)

    for n, draw in enumerate(draws):
        draw_ts = draw["timestamp"]

        click.echo(f"Draw {n+1} @ {convert(draw_ts - fight_start)}")
        click.echo("---\n")

        draw_dmg = get_dmg_events(
            args[0], draw_ts, draw_ts + 45000, copy.deepcopy(party)
        )
        res = sorted(
            [calc_dmg(x) for x in filter(lambda x: "events" in x, draw_dmg)],
            key=lambda x: x["total_damage"],
            reverse=True,
        )
        for i, job in enumerate(res):
            tcs = (
                "N/A"
                if job["start_timestamp"] is None
                else convert(job["start_timestamp"] - args[1])
            )

            click.echo(
                f'{i+1}. {job["name"]} ({job["job"]}), Total DMG: {job["total_damage"]}, Card @ {tcs}'
            )
        click.echo("\n")
