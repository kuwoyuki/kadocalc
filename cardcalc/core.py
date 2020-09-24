import requests
import ujson
import os


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
    if call not in ["fights", "events/summary", "events/damage-done" "tables/summary"]:
        return {}

    api_url = "https://www.fflogs.com/v1/report/{}/{}".format(call, report)

    data = fflogs_fetch(api_url, options)

    # If this is a fight list, we're done already
    if call in ["fights", "summary"]:
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
    Gets a list of tether buffs
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


def app():
    draws = get_draws("cZGBRqWgfPVKp3yx", 8081809, 8567936)
    print(draws)
