# About

The [League of Solvers (LoS)](http://los.npify.com) is a SAT solver
competition with matches every hour. (In the future we also hope to provide
other kinds of competitions.) Everyone is welcome to participate, either with
an existing solver or with their own. This program (`los_client`) is a client
to easily participate at the competition. [Learn more]
(http://los.npify.com/about)  about the League of Solvers.

# Getting Started

## Step 1. Installation

For Debian and many other modern operating systems you can use
```
    pipx install los_client
```
to install the client into a separate virtual environment.


## Step 2. Register a Solver
Register a solver and copy the token at [los.npify.com](http://los.npify.com).


## Step 3. Compete

If you have a solver that produces output compatible with the SAT competition
and accepts a cnf file as its only parameter, you just need to run
```
    los_client run --solver [path_to_solver] --token [token]
```
and wait for the next match to start.

If your solver is not compatible, you either need to write a script to adapt
or you can adjust the `los_client` code itself, see under Development.

You can also save and your configuration using

```
    los_client set --solver [path_to_solver] --token [token]
```

so the next time you only need to run

```
los_client run
```

# Development

Setup and run through the environment:

```
    pipx install uv
    git clone https://github.com/NPify/los_client.git
    cd los_client
    uv run los_client --help
```

