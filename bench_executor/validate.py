#!/usr/bin/env python3

"""
Validate the RDF graph output by comparing it with an expected graph.
"""

import os
from rdflib import Graph
from rdflib.compare import to_isomorphic
from bench_executor.logger import Logger


class Validate():
    """Validate the RDF graph by comparing it with an expected graph"""
    def __init__(self, data_path: str, config_path: str, directory: str,
                 verbose: bool, expect_failure: bool, environment=None):
        """Creates an instance of the Validate class.

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
        expect_failure : bool
            If a failure is expected.
        """
        self._data_path = os.path.abspath(data_path)
        self._config_path = os.path.abspath(config_path)
        self._logger = Logger(__name__, directory, verbose)

        os.umask(0)
        os.makedirs(os.path.join(self._data_path, 'validate'), exist_ok=True)

    @property
    def name(self):
        """Name of the class: Validate"""
        return __name__

    @property
    def root_mount_directory(self) -> str:
        """Subdirectory in the root directory of the case for Validate.

        Returns
        -------
        subdirectory : str
            Subdirectory of the root directory for Validate.

        """
        return __name__.lower()

    def compare_graphs(self, graph_file: str,
                       expected_graph_file: str) -> bool:
        """Compare a graph against an expected graph.

        Parameters
        ----------
        graph_file : str
            Path of the RDF graph file inside shared folder.
        expected_graph_file : str
            Path of the expected RDF graph file inside shared folder.

        Returns
        -------
        success : bool
            Whether the graphs match or not.
        """
        path = os.path.join(self._data_path, 'shared')
        os.umask(0)
        os.makedirs(path, exist_ok=True)

        self._logger.debug(f'Comparing {graph_file} against '
                           f'{expected_graph_file}')
        g1 = Graph().parse(os.path.join(path, graph_file))
        g2 = Graph().parse(os.path.join(path, expected_graph_file))
        iso1 = to_isomorphic(g1)
        iso2 = to_isomorphic(g2)

        return iso1 == iso2
