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
The example pipeline uses the following tools:

- MySQL as relational database
- RMLMapper as mapping engine
- Virtuoso as triple store

For detailed usage of this tool, please have a look at the 
[README](https://github.com/kg-construct/exectool/blob/main/README.md)
in the exectool repository.

## Tutorial: Adding your own tool

Adding your tool to exectool requires the following parts:

1. Package your tool as a Docker image and publish it on Docker Hub.
2. Create a Python class for your tool in the `bench_executor` folder.
3. Add some test cases for your tool, the test data goes in `bench_executor/data/test-cases` and the actual test goes into `tests`.

We will go through these steps for the RMLMapper:

**Step 1: package your tool as a Docker image**

Each tool _must_ expose a folder on `/data` where the tool can exchange data
such as mappings, files, etc. with the host system.
In case of the RMLMapper, the Dockerfile looks like this:

```
################################################################################
# RMLMapper
# https://github.com/RMLio/rmlmapper-java
################################################################################
FROM ubuntu:22.04
# Configure the RMLMapper version to use
ARG RMLMAPPER_VERSION
ARG RMLMAPPER_BUILD

# Install latest updates and dependencies
RUN apt-get update
RUN apt-get upgrade -y
RUN apt-get install -y openjdk-8-jdk less vim wget unzip

# Download RMLMapper release
RUN mkdir rmlmapper && wget -O rmlmapper/rmlmapper.jar https://github.com/RMLio/rmlmapper-java/releases/download/v${RMLMAPPER_VERSION}/rmlmapper-${RMLMAPPER_VERSION}-r${RMLMAPPER_BUILD}-all.jar

# Expose data folder
RUN mkdir /data

# Silent
CMD ["tail", "-f", "/dev/null"]
```

This Dockerfile uses Ubuntu 22.04 LTS as base and installs the dependencies for
the RMLMapper. After that, it downloads the RMLMapper jar from GitHub, the version
is made configurable through the `RMLMAPPER_VERSION` and `RMLMAPPER_BUILD` variables.
The Dockerfile also creates a folder in the root: `/data` which is used to exchange data with the host system.
This folder is crucial and ever tool must use and expose this path for exchange data!

Now we can build and publish our Docker image to Docker Hub:

```
# Build RMLMapper 6.0.0
docker build --build-arg RMLMAPPER_VERSION=6.0.0 --build-arg RMLMAPPER_BUILD=363 -t kgconstruct/rmlmapper:v6.0.0 .

# Publish Docker image under the "kgconstruct" organization
docker push kgconstruct/rmlmapper:v6.0.0
```

**Step 2: Create a Python class in the bench_executor folder**

Each tool has a slightly different interface to execute a [R2]RML mapping,
some tools can only handle only R2RML or RML mappings,
or require certain configuration files to operate.
These differences are abstracted by the Python class for each tool.

The Python class of the RMLMapper looks like this:

```
#!/usr/bin/env python3

"""
The RMLMapper executes RML rules to generate high quality Linked Data
from multiple originally (semi-)structured data sources.

**Website**: https://rml.io<br>
**Repository**: https://github.com/RMLio/rmlmapper-java
"""

import os
import psutil
from typing import Optional
from timeout_decorator import timeout, TimeoutError  # type: ignore
from bench_executor.container import Container
from bench_executor.logger import Logger

VERSION = '6.0.0'
TIMEOUT = 6 * 3600  # 6 hours


class RMLMapper(Container):
    """RMLMapper container for executing R2RML and RML mappings."""

    def __init__(self, data_path: str, config_path: str, directory: str,
                 verbose: bool):
        """Creates an instance of the RMLMapper class.

        Parameters
        ----------
        data_path : str
            Path to the data directory of the case.
        config_path : str
            Path to the config directory of the case.
        directory : str
            Path to the directory to store logs.
        verbose : bool
            Enable verbose logs.
        """
        self._data_path = os.path.abspath(data_path)
        self._config_path = os.path.abspath(config_path)
        self._logger = Logger(__name__, directory, verbose)
        self._verbose = verbose

        os.makedirs(os.path.join(self._data_path, 'rmlmapper'), exist_ok=True)
        super().__init__(f'kgconstruct/rmlmapper:v{VERSION}', 'RMLMapper',
                         self._logger,
                         volumes=[f'{self._data_path}/rmlmapper:/data',
                                  f'{self._data_path}/shared:/data/shared'])

    @property
    def root_mount_directory(self) -> str:
        """Subdirectory in the root directory of the case for RMLMapper.

        Returns
        -------
        subdirectory : str
            Subdirectory of the root directory for RMLMapper.

        """
        return __name__.lower()

    @timeout(TIMEOUT)
    def _execute_with_timeout(self, arguments: list) -> bool:
        """Execute a mapping with a provided timeout.

        Returns
        -------
        success : bool
            Whether the execution was successfull or not.
        """
        if self._verbose:
            arguments.append('-vvvvvvvvvvv')

        self._logger.info(f'Executing RMLMapper with arguments '
                          f'{" ".join(arguments)}')

        # Set Java heap to 1/2 of available memory instead of the default 1/4
        max_heap = int(psutil.virtual_memory().total * (1/2))

        # Execute command
        cmd = f'java -Xmx{max_heap} -Xms{max_heap} ' + \
              '-jar rmlmapper/rmlmapper.jar ' + \
              f'{" ".join(arguments)}'
        return self.run_and_wait_for_exit(cmd)

    def execute(self, arguments: list) -> bool:
        """Execute RMLMapper with given arguments.

        Parameters
        ----------
        arguments : list
            Arguments to supply to RMLMapper.

        Returns
        -------
        success : bool
            Whether the execution succeeded or not.
        """
        try:
            return self._execute_with_timeout(arguments)
        except TimeoutError:
            msg = f'Timeout ({TIMEOUT}s) reached for RMLMapper'
            self._logger.warning(msg)

        return False

    def execute_mapping(self,
                        mapping_file: str,
                        output_file: str,
                        serialization: str,
                        rdb_username: Optional[str] = None,
                        rdb_password: Optional[str] = None,
                        rdb_host: Optional[str] = None,
                        rdb_port: Optional[int] = None,
                        rdb_name: Optional[str] = None,
                        rdb_type: Optional[str] = None) -> bool:
        """Execute a mapping file with RMLMapper.

        N-Quads and N-Triples are currently supported as serialization
        format for RMLMapper.

        Parameters
        ----------
        mapping_file : str
            Path to the mapping file to execute.
        output_file : str
            Name of the output file to store the triples in.
        serialization : str
            Serialization format to use.
        rdb_username : Optional[str]
            Username for the database, required when a database is used as
            source.
        rdb_password : Optional[str]
            Password for the database, required when a database is used as
            source.
        rdb_host : Optional[str]
            Hostname for the database, required when a database is used as
            source.
        rdb_port : Optional[int]
            Port for the database, required when a database is used as source.
        rdb_name : Optional[str]
            Database name for the database, required when a database is used as
            source.
        rdb_type : Optional[str]
            Database type, required when a database is used as source.

        Returns
        -------
        success : bool
            Whether the execution was successfull or not.
        """
        arguments = ['-m', os.path.join('/data/shared/', mapping_file),
                     '-s', serialization,
                     '-o', os.path.join('/data/shared/', output_file),
                     '-d']  # Enable duplicate removal

        if rdb_username is not None and rdb_password is not None \
                and rdb_host is not None and rdb_port is not None \
                and rdb_name is not None and rdb_type is not None:

            arguments.append('-u')
            arguments.append(rdb_username)
            arguments.append('-p')
            arguments.append(rdb_password)

            parameters = ''
            if rdb_type == 'MySQL':
                protocol = 'jdbc:mysql'
                parameters = '?allowPublicKeyRetrieval=true&useSSL=false'
            elif rdb_type == 'PostgreSQL':
                protocol = 'jdbc:postgresql'
            else:
                raise ValueError(f'Unknown RDB type: "{rdb_type}"')
            rdb_dsn = f'{protocol}://{rdb_host}:{rdb_port}/' + \
                      f'{rdb_name}{parameters}'
            arguments.append('-dsn')
            arguments.append(rdb_dsn)

        return self.execute(arguments)
```

The Python class for the RMLMapper abstracts the following items so they are
configured consistently:

- Java heap size: set to 50% of the available RAM memory.
This avoids differences among Java versions and Java configurations among different operating systems.
- CLI arguments: provide the path to the mapping file in the exposed `/data/` directory and the verbosity of the logs.
In case of an R2RML mapping, the required CLI arguments to access the database e.g. username, password, host, port are automatically added as well.

**Step 3: add tests for your tool**

It is preferable to add some tests for your tool so you know
that the tool is executed correctly.

2 directories are important for adding tests:

- `bench_executor/data/test-cases`: add here the data necessary to execute your test.
Have a look there, several tests are already created and use data from there.
- `tests`: add here your actual test e.g. execute a mapping to transform a CSV file into N-Triples.

For the RMLMapper, several test cases exist from executing 
the Python abstraction class to perform a complete execution of a pipeline.
Have a look around in the mentioned directories to see how to add your tool.

## Installation

*This installation guide is tested with Ubuntu 22.04 LTS, but other Linux distributions work as well.*

**Step 1: Install dependencies**

```
sudo apt install zlib1g zlib1g-dev libpq-dev libjpeg-dev python3-pip docker.io
pip install --user -r requirements.txt
```

**Step 2: Configure Docker**

```
# Add user to docker group
sudo groupadd docker
sudo usermod -aG docker $USER
```

Do not forget to logout so the user groups are properly updated!

**Step 3: Verify installation**

```
# Run all tests
cd bench_executor
./tests/unit_tests
```

## License

Licensed under the [MIT license](./LICENSE)<br>
Written by Dylan Van Assche (dylan.vanassche@ugent.be)
