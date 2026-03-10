## What is it?
UiPath Coded Process to run Power Automate Flows.

## How to use it in UiPath Maestro?
In Maestro service task, choose "Start and wait for agent" action and then select this process. Fill in the url argument with the trigger url of the flow to be invoked. This will invoke the flow using HTTP trigger and then wait for completion.
* json: Input arguments in JSON format
* timeout: Wait for completion timeout
* url: Trigger URL of the flow

<img width="633" height="698" alt="image" src="https://github.com/user-attachments/assets/5bb839c9-dd3c-4de1-84b5-925701b3c8ce" />

## How to build
1. $ cd RunPowerAutomateFlow
2. $ uv venv
3. $ source .venv/bin/activate
4. $ uv add uipath
5. $ uipath pack
