#!/usr/bin/env python3
"""
This module holds the Stats class which is responsible for generating
staticstics from executed cases. It will automatically aggregate all runs of an
executed case to generate an `aggregated.csv` and `summary.csv` files which can
be used to compare various cases with each other.

- `aggregated.csv`: For each run of a case, the median execution time of each
  step is calculated. For each step, the results of the run with the median
  execution time is used to assemble the aggregated results.
- `summary.csv`: The summary is similar to the previous file, but provides a
  single result for each step to immediately see how long the step took, how
  many samples are provided for the step, etc.
"""

import os
from glob import glob
from statistics import median
from csv import DictWriter, DictReader
from typing import List
from bench_executor.collector import FIELDNAMES, METRICS_FILE_NAME
from bench_executor.logger import Logger

METRICS_AGGREGATED_FILE_NAME = 'aggregated.csv'
METRICS_SUMMARY_FILE_NAME = 'summary.csv'
FIELDNAMES_FLOAT = ['timestamp', 'cpu_user', 'cpu_system', 'cpu_idle',
                    'cpu_iowait', 'cpu_user_system']
FIELDNAMES_INT = ['index', 'step', 'version', 'memory_ram', 'memory_swap',
                  'memory_ram_swap', 'disk_read_count', 'disk_write_count',
                  'disk_read_bytes', 'disk_write_bytes', 'disk_read_time',
                  'disk_write_time', 'disk_busy_time',
                  'network_received_count', 'network_sent_count',
                  'network_received_bytes', 'network_sent_bytes',
                  'network_received_error', 'network_sent_error',
                  'network_received_drop', 'network_sent_drop']
FIELDNAMES_SUMMARY = [
    'number_of_samples',
    'step',
    'duration',
    'version',
    'cpu_user_diff',
    'cpu_system_diff',
    'cpu_user_system_diff',
    'cpu_idle_diff',
    'cpu_iowait_diff',
    'memory_ram_max',
    'memory_swap_max',
    'memory_ram_swap_max',
    'memory_ram_min',
    'memory_swap_min',
    'memory_ram_swap_min',
    'disk_read_count_diff',
    'disk_write_count_diff',
    'disk_read_bytes_diff',
    'disk_write_bytes_diff',
    'disk_read_time_diff',
    'disk_write_time_diff',
    'disk_busy_time_diff',
    'network_received_count_diff',
    'network_sent_count_diff',
    'network_received_bytes_diff',
    'network_sent_bytes_diff',
    'network_received_error_diff',
    'network_sent_error_diff',
    'network_received_drop_diff',
    'network_sent_drop_diff'
]
ROUND = 4

#
# Generate stats from the result runs by aggregating it on
# median execution time for each step. Processing is done for each step per
# run and unnecessary values are skipped to reduce the memory consumption.
#
# The median run is available in 'aggregated.csv' while a summarized version
# which only reports the diff or max value of each step in 'summary.csv'
#


class Stats():
    """Generate statistics for an executed case."""

    def __init__(self, results_path: str, number_of_steps: int,
                 directory: str, verbose: bool):
        """Create an instance of the Stats class.

        Parameters
        ----------
        results_path : str
            The path to the results directory of the case
        number_of_steps : int
            The number of steps of the case
        directory : str
            The path to the directory where the logs must be stored.
        verbose : bool
            Enable verbose logs.
        """
        self._results_path = os.path.abspath(results_path)
        self._number_of_steps = number_of_steps
        self._logger = Logger(__name__, directory, verbose)

        if not os.path.exists(results_path):
            msg = f'Results do not exist: {results_path}'
            self._logger.error(msg)
            raise ValueError(msg)

    def _parse_field(self, field, value):
        """Parse the field of the metrics field in a Python data type."""
        try:
            if field in FIELDNAMES_FLOAT:
                return float(value)
            elif field in FIELDNAMES_INT:
                return int(value)
            else:
                msg = f'Field "{field}" type is unknown'
                self._logger.error(msg)
                raise ValueError(msg)
        except TypeError:
            return -1

    def _parse_v2(self, run_path, fields=FIELDNAMES, step=None):
        """Parse the CSV metrics file in v2 format."""
        data = []

        metrics_file = os.path.join(run_path, METRICS_FILE_NAME)
        if not os.path.exists(metrics_file):
            self._logger.error(f'Metrics file "{metrics_file}" does not exist')
            return []

        # Filter the fields we want from above, this way we don't load all
        # the data in memory during processing.
        with open(metrics_file, 'r') as f:
            reader = DictReader(f)
            for line in reader:
                corrupt: bool = False

                # Skip steps we don't want to parse
                if step is not None and \
                   step != self._parse_field('step', line['step']):
                    continue

                # Filter on field names
                filtered = {key: line[key] for key in fields}
                entry = {}
                for key, value in filtered.items():
                    v = self._parse_field(key, value)
                    if v == -1:
                        corrupt = True
                        msg = f'Corrupt entry {key} with value {value} in ' + \
                              f'{metrics_file}, skipped'
                        self._logger.info(msg)
                        break

                    entry[key] = v

                if not corrupt:
                    data.append(entry)

        return data

    def aggregate(self) -> bool:
        """Aggregate the metrics of the different runs of a case.

        Find the median execution time of each step across all runs and extract
        the step from the run which has this median execution time to assemble
        an aggregated version and summary version of the case's metrics.

        Returns
        -------
        success : bool
            Whether the aggregation was successfully or not.
        """
        # Find each median step of all runs before extracting more data for
        # memory consumption reasons
        runs = []
        for run_path in glob(f'{self._results_path}/run_*/'):
            # Extract run number
            try:
                run_folder: str = os.path.split(os.path.dirname(run_path))[-1]
                run_id: int = int(run_folder.replace('run_', ''))
            except ValueError:
                self._logger.error(f'Run "{run_id}" is not a number')
                return False

            # Extract steps and timestamps of this run
            data = self._parse_v2(run_path, fields=['step', 'timestamp'])

            # Calculate timestamp diff for each step
            step = 1
            timestamps = []
            for i in range(self._number_of_steps):
                timestamps.append(0.0)
            step_end = 0.0
            step_begin = 0.0
            for entry in data:
                entry_step = entry['step']
                assert (entry_step >= step), 'Entry step decreased over time'

                # Next step
                if entry_step > step:
                    # Calculate diff of current step if at least 2 entries
                    # for the step exist, if not the diff is 0.0 and we fall
                    # back to the step_begin timestamp which will make sure we
                    # use the run with the timestamp that is the median of all
                    # runs. For example: [4.5, 5.0, 6.5] will return run 2 as
                    # 5.0 is the median.
                    diff = step_end - step_begin
                    if diff == 0.0:
                        self._logger.warning(f'Only 1 entry for step {step} '
                                             f'found, falling back to median '
                                             f'timestamp instead of diff')
                        diff = step_begin

                    timestamps[step] = diff

                    # Reset for next step
                    step = entry_step
                    step_begin = entry['timestamp']
                    step_end = entry['timestamp']
                # step_end keeps increasing until the step changes
                else:
                    step_end = entry['timestamp']
            # Final step does not cause an increment, add manually
            timestamps[step-1] = step_end - step_begin
            print(len(timestamps))
            runs.append((run_id, timestamps))

        # Statistics rely on uneven number of runs
        assert (len(runs) % 2 != 0), 'Number of runs should never be even'

        # Runs are unsorted as glob does not have a fixed order, sort them
        # based on run number in tuple
        runs.sort(key=lambda element: element[0])

        # Find median for each step across runs
        timestamps_by_step: List[List[float]] = []
        for step_index in range(self._number_of_steps):
            timestamps_by_step.append([])

        for run in runs:
            run_id = run[0]
            timestamps = run[1]

            # Do not process incomplete runs
            msg = f'Number of steps ({self._number_of_steps}) does not ' + \
                  'match with extracted steps of ' + \
                  f'run ({len(timestamps)}). Skipping run {run_id}'
            assert (len(timestamps) == self._number_of_steps), msg

            # Create list of timestamps for each step from all runs
            for step_index in range(self._number_of_steps):
                timestamps_by_step[step_index].append(timestamps[step_index])

        # Create a list of our steps with the run_id which has the median value
        # for that step
        aggregated_entries = []
        summary_entries = []
        index_number = 1
        for step_index, step_timestamps in enumerate(timestamps_by_step):
            # We ensure that the number of runs is always uneven so the median
            # is always a measured data point instead of the average of 2 data
            # points with even number of runs
            median_run_id = timestamps_by_step[step_index] \
                            .index(median(step_timestamps)) + 1
            median_run_path = os.path.join(self._results_path,
                                           f'run_{median_run_id}')
            median_step_data = self._parse_v2(median_run_path,
                                              step=step_index + 1)

            # Rewrite indexes to match new number of samples
            for entry in median_step_data:
                entry['index'] = index_number

                aggregated_entries.append(entry)
                index_number += 1

        # Summary data of a step: diff per step
        for step_index, step_timestamps in enumerate(timestamps_by_step):
            summary = {}
            median_run_id = timestamps_by_step[step_index] \
                .index(median(step_timestamps)) + 1
            median_run_path = os.path.join(self._results_path,
                                           f'run_{median_run_id}')
            median_step_data = self._parse_v2(median_run_path,
                                              step=step_index + 1)
            for field in FIELDNAMES:
                # Report max memory peak for this step
                if 'memory' in field:
                    values = []
                    for data in median_step_data:
                        values.append(data[field])

                    try:
                        summary[f'{field}_min'] = min(values)
                        summary[f'{field}_max'] = max(values)
                    except ValueError:
                        summary[f'{field}_min'] = 0.0
                        summary[f'{field}_max'] = 0.0
                # Leave some fields like they are
                elif field == 'step':
                    step = step_index + 1
                    summary[field] = step
                    if median_step_data:
                        print(step, median_step_data[0][field])
                        msg = f'Step number mismatch, expected step {step},' \
                              f' got step {median_step_data[0][field]}'
                        assert (step == median_step_data[0][field]), msg
                elif field == 'version':
                    summary[field] = 2
                # All other fields are accumulated data values for which we
                # report the diff for the step
                else:
                    has_samples = True

                    try:
                        first = median_step_data[0][field]
                        last = median_step_data[-1][field]
                        diff = round(last - first, ROUND)
                    except IndexError:
                        diff = 0.0
                        has_samples = False

                    if field == 'index':
                        # diff will be 0 for 1 sample, but we have this sample,
                        # so include it
                        if has_samples:
                            summary['number_of_samples'] = diff + 1
                        else:
                            summary['number_of_samples'] = 0
                    elif field == 'timestamp':
                        summary['duration'] = diff
                    else:
                        summary[f'{field}_diff'] = diff
            summary_entries.append(summary)

        aggregated_file = os.path.join(self._results_path,
                                       METRICS_AGGREGATED_FILE_NAME)
        summary_file = os.path.join(self._results_path,
                                    METRICS_SUMMARY_FILE_NAME)

        # Store aggregated data
        with open(aggregated_file, 'w') as f:
            writer = DictWriter(f, fieldnames=FIELDNAMES)
            writer.writeheader()
            for entry in aggregated_entries:
                writer.writerow(entry)

        # Store summary data
        with open(summary_file, 'w') as f:
            writer = DictWriter(f, fieldnames=FIELDNAMES_SUMMARY)
            writer.writeheader()
            for entry in summary_entries:
                writer.writerow(entry)

        return True
