import asyncio
from pathlib import Path

import pytest
from websockets import connect

from los_client import models
from los_client.cli import SatCLI
from los_client.client import Client
from los_client.config import CLIConfig

TEST_INPUT = Path(__file__).parent / "test_input"


@pytest.mark.skip(reason="This test requires solver binaries to be present")
def test_register_and_run() -> None:
    config_path = TEST_INPUT / "run_test_config.json"
    config = CLIConfig.load_config(config_path)
    cli = SatCLI(config)
    client = Client(cli.config)

    async def helper() -> None:
        async with connect(str(client.config.host)) as ws:
            models.Welcome.model_validate_json(await ws.recv())
            await client.register_solvers(ws)
            instance = await client.get_instance(ws)
            await client.run_solver(ws, config.solvers[0], instance)

    asyncio.run(helper())
