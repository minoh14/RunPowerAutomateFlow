from dataclasses import dataclass
from typing import Optional

from run_flow_trigger import run_flow_by_trigger
from run_flow_id import run_flow_by_id


@dataclass
class FlowInput:
    json: str  # input arguments as JSON string
    timeout: int  # in seconds
    url: Optional[str] = None  # Trigger URL of Power Automate Flow
    tenant_id: Optional[str] = None  # Tenant ID for authentication
    client_id: Optional[str] = None  # Client ID for authentication
    client_secret: Optional[str] = None  # Client Secret for authentication
    environment_id: Optional[str] = None  # Environment ID for Power Automate Flow
    flow_id: Optional[str] = None  # Flow ID of Power Automate Flow


@dataclass
class FlowOutput:
    json: str  # output from Power Automate Flow as JSON string


def main(input: FlowInput) -> FlowOutput:
    if input.url:
        result = run_flow_by_trigger(input.json, input.url, input.timeout)
    else:
        result = run_flow_by_id(
            input.json,
            input.tenant_id,
            input.client_id,
            input.client_secret,
            input.environment_id,
            input.flow_id,
            input.timeout,
        )
    return FlowOutput(json=result)


if __name__ == "__main__":
    main(FlowInput(json='{"name": "John Doe"}', timeout=120))
