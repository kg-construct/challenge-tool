#!/usr/bin/env python3

"""
This module holds the Container and ContainerManager classes. The Container
class is responsible for abstracting the Docker containers and allow running
containers easily and make sure they are initialized before using them.
The Containermanager class allows to create container networks, list all
running containers and stop them.
"""

import os
import docker  # type: ignore
from time import time, sleep
from typing import List, Tuple
from bench_executor.logger import Logger

WAIT_TIME = 1  # seconds
TIMEOUT_TIME = 600  # seconds
NETWORK_NAME = 'bench_executor'
DOCKER_HOST = os.getenv('DOCKER_HOST', 'unix:///var/run/docker.sock')


class ContainerManager():
    """Manage containers and networks."""

    def __init__(self):
        """Creates an instance of the ContainerManager class."""

    def list_all(self):
        """List all available containers."""
        with docker.DockerClient(base_url=DOCKER_HOST) as client:
            return client.containers.list(all=True)

    def stop_all(self):
        """Stop all containers."""
        stopped = False
        removed = False

        for container in self.list_all():
            try:
                container.stop()
                stopped = True
            except docker.errors.APIError:
                pass
            try:
                container.remove()
                removed = True
            except docker.errors.APIError:
                pass
            print(f'Container {container.name}: stopped: {stopped} '
                  f'removed: {removed}')

    def create_network(self, name: str):
        """Create a container network.

        Parameters
        ----------
        name : str
            Name of the network
        """
        with docker.DockerClient(base_url=DOCKER_HOST) as client:
            try:
                client.networks.get(name)
            except docker.errors.NotFound:
                client.networks.create(name)


class Container():
    """Container abstracts a Docker container

    Abstract how to run a command in a container, start or stop a container,
    or retrieve logs. Also allow to wait for a certain log entry to appear or
    exit successfully.
    """

    def __init__(self, container: str, name: str, logger: Logger,
                 ports: dict = {}, environment: dict = {},
                 volumes: List[str] = []):
        """Creates an instance of the Container class.

        Parameters
        ----------
        container : str
            Container ID.
        name : str
            Pretty name of the container.
        logger : Logger
            Logger class to use for container logs.
        ports : dict
            Ports mapping of the container onto the host.
        volumes : list
            Volumes mapping of the container onto the host.
        """
        self._manager = ContainerManager()
        self._container = None
        self._container_name = container
        self._name = name
        self._ports = ports
        self._volumes = volumes
        self._environment = environment
        self._proc_pid = None
        self._long_id = None
        self._cgroups_mode = None
        self._cgroups_dir = None
        self._started = False
        self._logger = logger

        # create network if not exist
        self._manager.create_network(NETWORK_NAME)

    @property
    def started(self) -> bool:
        """Indicates if the container is already started"""
        return self._started

    @property
    def name(self) -> str:
        """The pretty name of the container"""
        return self._name

    def run(self, command: str = '', detach=True) -> bool:
        """Run the container.

        This is used for containers which are long running to provide services
        such as a database or endpoint.

        Parameters
        ----------
        command : str
            The command to execute in the container, optionally and defaults to
            no command.
        detach : bool
            If the container may run in the background, default True.

        Returns
        -------
        success : bool
            Whether running the container was successfull or not.
        """
        try:
            e = self._environment
            v = self._volumes
            with docker.DockerClient(base_url=DOCKER_HOST) as client:
                self._container = client.containers.run(self._container_name,
                                                        command,
                                                        name=self._name,
                                                        detach=detach,
                                                        ports=self._ports,
                                                        network=NETWORK_NAME,
                                                        environment=e,
                                                        volumes=v)
            self._started = (self._container is not None)
            return True
        except docker.errors.APIError as e:
            self._logger.error(f'Failed to start container: {e}')

        self._logger.error(f'Starting container "{self._name}" failed!')
        return False

    def exec(self, command: str) -> Tuple[bool, List[str]]:
        """Execute a command in the container.

        Parameters
        ----------
        command : str
            The command to execute in the container.

        Returns
        -------
        success : bool
            Whether the command was executed successfully or not.
        logs : list
            The logs of the container for executing the command.
        """
        logs: List[str] = []

        try:
            if self._container is None:
                self._logger.error('Container is not initialized yet')
                return False, []
            exit_code, output = self._container.exec_run(command)
            logs = output.decode()
            for line in logs.split('\n'):
                self._logger.debug(line.strip())
            if exit_code == 0:
                return True, logs
        except docker.errors.APIError as e:
            self._logger.error(f'Failed to execute command: {e}')

        return False, logs

    def run_and_wait_for_log(self, log_line: str, command: str = '') -> bool:
        """Run the container and wait for a log line to appear.

        This blocks until the container's log contains the `log_line`.

        Parameters
        ----------
        log_line : str
            The log line to wait for in the logs.
        command : str
            The command to execute in the container, optionally and defaults to
            no command.

        Returns
        -------
        success : bool
            Whether the container exited with status code 0 or not.
        """
        if not self.run(command):
            self._logger.error(f'Command "{command}" failed')
            return False

        if self._container is None:
            self._logger.error('Container is not initialized yet')
            return False

        start = time()
        found_line = False
        logs = self._container.logs(stream=True, follow=True)
        lines = []
        if logs is not None:
            for line in logs:
                line = line.decode().strip()
                lines.append(line)
                self._logger.debug(line)

                if time() - start > TIMEOUT_TIME:
                    msg = f'Starting container "{self._name}" timed out!'
                    self._logger.error(msg)
                    break

                if log_line in line:
                    found_line = True
                    break

            logs.close()
            if found_line:
                sleep(WAIT_TIME)
                return True

        # Logs are collected on success, log them on failure
        self._logger.error(f'Waiting for container "{self._name}" failed!')
        for line in lines:
            self._logger.error(line)
        return False

    def run_and_wait_for_exit(self, command: str = '') -> bool:
        """Run the container and wait for exit

        This blocks until the container exit and gives a status code.

        Parameters
        ----------
        command : str
            The command to execute in the container, optionally and defaults to
            no command.

        Returns
        -------
       success : bool
            Whether the container exited with status code 0 or not.
        """
        if not self.run(command):
            return False

        if self._container is None:
            self._logger.error('Container is not initialized yet')
            return False

        status_code = self._container.wait()['StatusCode']
        logs = self._container.logs(stream=True, follow=True)
        if logs is not None:
            for line in logs:
                line = line.decode().strip()
                # On success, logs are collected when the container is stopped.
                if status_code != 0:
                    self._logger.error(line)
            logs.close()

        if status_code == 0:
            self.stop()
            return True

        self._logger.error('Command failed while waiting for exit with status '
                           f'code: {status_code}')
        return False

    def stop(self) -> bool:
        """Stop a running container

        Stops the container and removes it, including its volumes.

        Returns
        -------
        success : bool
            Whether stopping the container was successfull or not.
        """
        try:
            if self._container is not None:
                logs = self._container.logs()
                if logs is not None:
                    logs = logs.decode()
                    for line in logs.split('\n'):
                        self._logger.debug(line)

                self._container.stop()
                self._container.remove(v=True)
            return True
        # Containers which are already stopped will raise an error which we can
        # ignore
        except docker.errors.APIError:
            pass

        return True
