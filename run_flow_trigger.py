# Invokes Power Automate Flow using its trigger URL

import requests


def run_flow_by_trigger(input_json: str, trigger_url: str, timeout: int) -> str:
    try:
        response = requests.post(
            url=trigger_url,
            headers={"Content-Type": "application/json"},
            data=input_json,
            timeout=timeout,
        )
        response.raise_for_status()
        return response.json()
    except requests.HTTPError as e:
        print(f"HTTP Error: {e.response.status_code} - {e.response.text}")
        raise
