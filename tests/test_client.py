"""
def test_register_and_run(capfd: CaptureFixture) -> None:
    config = CLIConfig()
    cli = SatCLI(config)
    cli.config.solver = Path("solver")
    cli.config.output = Path("output")
    cli.config.token = "D1BwDpACZ4kIUnY_QEohmg"
    client = Client(cli.config)

    async def helper() -> None:
        async with connect(str(client.config.host)) as ws:
            models.Welcome.model_validate_json(await ws.recv())
            await client.register_solver(ws)
            await client.run_solver(ws,True)

    asyncio.run(helper())

    captured = capfd.readouterr()
    assert "Solver registered" in captured.out
    assert "Solution submitted" in captured.out
"""
