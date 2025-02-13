# About

The [League of Solvers (LoS)](http://los.npify.com) is a SAT solver
competition with matches every hour. (In the future we also hope to provide
other kinds of competitions.) Everyone is welcome to participate, either with
an existing solver or with their own. This program (`los_client`) is a client
to easily participate at the competition.

# Getting Started

## Step 1. Installation

It is recommended to install via `pipx` so that the client can run in a seperate environment.
```
sudo apt install pipx
```

Once pipx is installed you can install the client via
```
pipx install los-client
```


## Step 2. Register a Solver
Register a solver and copy the token at [los.npify.com](http://los.npify.com).


## Step 3. Compete

#### Global Options
```

--config PATH    # Configuration file (default: configs/default.json)
--version       # Show version information
-v, --verbose   # Print verbose information
--debug         # Enable debug information
--quiet         # Disable countdown display
--write_outputs # Write problem and solver outputs
```
All commands accept the global options. If no --config path is given, then default configuration file is used.


If you have a solver that produces output compatible with the SAT competition
and accepts a cnf file as its only parameter, then you need to add it to the configuration first. If you're using a custom config file then it will be automatically created when you attempt to modify it.

#### Solver Management

Add New Solver

```
los_client add [token] [solver] [--output output_path]
```

Modify Existing Solver

```
los_client modify [token] --solver [new_solver] --token [new_solver] --new_output [new_output_path]
```
Delete Solver

```
los_client delete [token]
``` 
Set main output folder where all solver outputs and problem instances are placed.

```
los_client output_folder [output_folder_path]
```
Set Problem Path

```
los_client problem_path [problem_path]
```
Once you've finished configuring the solvers you can run the client
```
los_client run
```
To show the current configuration
```

los_client show
```




If your solver is not compatible, you either need to write a script to adapt
or you can adjust the `los_client` code itself, see under Development.

# Development

Setup and run through the environment:

```
pipx install uv
git clone https://github.com/NPify/los_client.git
cd los_client
uv run los_client --help
```

