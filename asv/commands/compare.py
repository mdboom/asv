# -*- coding: utf-8 -*-
# Licensed under a 3-clause BSD style license - see LICENSE.rst

from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

from . import Command
from ..machine import Machine
from ..repo import get_repo
from ..results import iter_results_for_machine
from ..util import hash_equal, human_time
from ..console import color_print


class Compare(Command):

    @classmethod
    def setup_arguments(cls, subparsers):
        parser = subparsers.add_parser(
            "compare",
            help="""Compare the benchmark results between two revisions""",
            description="Compare two sets of results")

        parser.add_argument(
            'revision1', nargs=1,
            help="""The reference revision.""")
        parser.add_argument(
            'revision2', nargs=1,
            help="""The revision being compared""")
        parser.add_argument(
            '--threshold', '-t', nargs='?', type=float, default=2,
            help="""The threshold to use to color-code divergent results. This
                    is a factor, so for example setting this to 2 will
                    highlight all results differing by more than a factor of
                    2.""")

        parser.set_defaults(func=cls.run_from_args)

        return parser

    @classmethod
    def run_from_conf_args(cls, conf, args):
        return cls.run(
            conf=conf, revision1=args.revision1[0], revision2=args.revision2[0], threshold=args.threshold)

    @classmethod
    def run(cls, conf, revision1, revision2, threshold=2, _machine_file=None):

        machine_params = Machine.load(_path=_machine_file, interactive=True)

        repo = get_repo(conf)

        commit_hash_1 = repo.get_hash_from_tag(revision1)
        commit_hash_2 = repo.get_hash_from_tag(revision2)

        results_1 = None
        results_2 = None

        for result in iter_results_for_machine(conf.results_dir, machine_params.machine):
            if hash_equal(commit_hash_1, result.commit_hash):
                results_1 = result
            if hash_equal(commit_hash_2, result.commit_hash):
                results_2 = result

        if results_1 is None:
            raise ValueError("Did not find results for commit {0}".format(commit_hash_1))

        if results_2 is None:
            raise ValueError("Did not find results for commit {0}".format(commit_hash_2))

        benchmarks_1 = set(results_1.results.keys())
        benchmarks_2 = set(results_2.results.keys())

        common_benchmarks = sorted(list(benchmarks_1 & benchmarks_2))

        print("")
        print("  before     after    speedup")

        for benchmark in common_benchmarks:

            time_1 = results_1.results[benchmark]
            time_2 = results_2.results[benchmark]

            if time_1 is None or time_2 is None:
                ratio = 'n/a'
            else:
                ratio = "{0:6.2f}".format(time_2 / time_1)

            if time_1 is None and time_2 is not None:
                color = 'green'
            elif time_1 is not None and time_2 is None:
                color = 'red'
            elif time_2 < time_1 / threshold:
                color = 'green'
            elif time_2 > time_1 * threshold:
                color = 'red'
            else:
                color = 'default'

            color_print("{0:>9s} {1:>9s} {2:>9s}  ".format('failed' if time_1 is None else human_time(time_1),
                                                   'failed' if time_2 is None else human_time(time_2),
                                                    ratio), color, end='')
            print(benchmark)