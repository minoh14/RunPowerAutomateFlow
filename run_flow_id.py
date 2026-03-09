# Invokes Power Automate Flow using its ID

from power_automate import PowerAutomateClient


def run_flow_by_id(
    input_json: str,
    tenant_id: str,
    client_id: str,
    client_secret: str,
    environment_id: str,
    flow_id: str,
    timeout: int,
) -> str:

    client = PowerAutomateClient(
        tenant_id=tenant_id,
        client_id=client_id,
        client_secret=client_secret,
        environment_id=environment_id,
    )

    result = client.run_flow_sync(flow_id=flow_id, body=input_json, timeout=timeout)

    if result.succeeded:
        print(f"Success. Elapsed time: {result.duration:.1f} seconds")
    else:
        print(f"Failed. Elapsed time: {result.duration:.1f} seconds")
        print(f"Error: {result.error_message}")

    return result
