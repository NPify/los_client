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

To use this client to the League of Solvers your solver needs to

 * accept an instances in DIMACS CNF format ([description](https://people.sc.fsu.edu/~jburkardt/data/cnf/cnf.html)) as the only parameter
 * produce output that is compatible with the [SAT competition](https://satcompetition.github.io/2024/output.html)

If your solver is not compatible, you either need to write a script to adapt
or you can adjust the `los_client` code itself, see under Development.

To add a solver, you use

```
los_client add [token] [solver]
```

where `[token]` is obtained in the previous step and `[solver]` is the path to
your solver binary or wrapper script.

Once you've finished configuring the solver you can run the client via

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

