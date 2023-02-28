# KGCW Challenge Tool

The KGCW Challenge Tool is based on the EXEC (EXperiment ExeCutor). 
[EXEC](https://github.com/kg-construct/exectool) is a simple tool 
to execute benchmarks on tools which are running in Docker.
EXEC exposes a CLI interface `exectool`.

## Quick Start KGCW Challenge 2023

1. Follow the [installation instructions](./README.md#installation) to install the tool.

2. Download the data of the KGCW Challenge 2023 by running the tool as followed:
```
./exectool download-challenge-2023
```
This will fetch the data, mappings, and other files from Zenodo and unpack them.
Make sure you have sufficient disk space left.

3. Execute the example pipeline included in the challenge:
```
./exectool run --runs=5 --root=eswc-kgc-challenge-2023
```
The tool will execute all cases in the
challenge (`--root=eswc-kgc-challenge-2023`)
five times (`--runs=5`) and report its progress to stdout of your command line.

For detailed usage of this tool, please have a look at the 
[README](https://github.com/kg-construct/exectool/blob/main/README.md)
in the exectool repository.

## Installation

**Ubuntu 22.04 LTS**

1. Install dependencies

```
sudo apt install zlib1g zlib1g-dev libpq-dev libjpeg-dev python3-pip docker.io
pip install --user -r requirements.txt
```

2. Configure Docker

```
# Add user to docker group
sudo groupadd docker
sudo usermod -aG docker $USER
```

Do not forget to logout so the user groups are properly updated!

3. Verify installation

```
# Run all tests
cd bench_executor
./tests/unit_tests
```

## License

Licensed under the [MIT license](./LICENSE)<br>
Written by Dylan Van Assche (dylan.vanassche@ugent.be)
