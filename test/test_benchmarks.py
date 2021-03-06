# -*- coding: utf-8 -*-
# Licensed under a 3-clause BSD style license - see LICENSE.rst

from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import os
import shutil
from os.path import join, dirname

import pstats
import pytest
import six

from asv import benchmarks
from asv import config
from asv import environment
from asv import util

from . import tools

BENCHMARK_DIR = join(dirname(__file__), 'benchmark')

INVALID_BENCHMARK_DIR = join(
    dirname(__file__), 'benchmark.invalid')

ASV_CONF_JSON = {
    'project': 'asv'
    }


def test_find_benchmarks(tmpdir):
    tmpdir = six.text_type(tmpdir)
    os.chdir(tmpdir)

    shutil.copytree(BENCHMARK_DIR, 'benchmark')

    d = {}
    d.update(ASV_CONF_JSON)
    d['env_dir'] = "env"
    d['benchmark_dir'] = 'benchmark'
    d['repo'] = tools.generate_test_repo(tmpdir, [0]).path
    conf = config.Config.from_json(d)

    envs = list(environment.get_environments(conf, None))

    b = benchmarks.Benchmarks(conf, envs, regex='secondary')
    assert len(b) == 3

    b = benchmarks.Benchmarks(conf, envs, regex='example')
    assert len(b) == 22

    b = benchmarks.Benchmarks(conf, envs, regex='time_example_benchmark_1')
    assert len(b) == 2

    b = benchmarks.Benchmarks(conf, envs, regex=['time_example_benchmark_1',
                                                 'some regexp that does not match anything'])
    assert len(b) == 2

    b = benchmarks.Benchmarks(conf, envs)
    assert len(b) == 26

    b = benchmarks.Benchmarks(conf, envs)
    times = b.run_benchmarks(envs[0], profile=True, show_stderr=True)

    assert len(times) == len(b)
    assert times[
        'time_examples.TimeSuite.time_example_benchmark_1']['result'] is not None
    # Benchmarks that raise exceptions should have a time of "None"
    assert times[
        'time_secondary.TimeSecondary.time_exception']['result'] is None
    assert times[
        'subdir.time_subdir.time_foo']['result'] is not None
    assert times[
        'mem_examples.mem_list']['result'] > 1000
    assert times[
        'time_secondary.track_value']['result'] == 42.0
    assert 'profile' in times[
        'time_secondary.track_value']
    assert 'stderr' in times[
        'time_examples.time_with_warnings']
    assert times['time_examples.time_with_warnings']['errcode'] != 0

    assert times['params_examples.track_param']['result']['params'] == [["<class 'benchmark.params_examples.ClassOne'>",
                                                                         "<class 'benchmark.params_examples.ClassTwo'>"]]
    assert times['params_examples.track_param']['result']['result'] == [42, 42]

    assert times['params_examples.mem_param']['result']['params'] == [['10', '20'], ['2', '3']]
    assert len(times['params_examples.mem_param']['result']['result']) == 2*2

    assert times['params_examples.ParamSuite.track_value']['result']['params'] == [["'a'", "'b'", "'c'"]]
    assert times['params_examples.ParamSuite.track_value']['result']['result'] == [1+0, 2+0, 3+0]

    assert isinstance(times['params_examples.TuningTest.time_it']['result']['result'][0], float)

    assert isinstance(times['params_examples.time_skip']['result']['result'][0], float)
    assert isinstance(times['params_examples.time_skip']['result']['result'][1], float)
    assert util.is_nan(times['params_examples.time_skip']['result']['result'][2])

    assert times['peakmem_examples.peakmem_list']['result'] >= 4 * 2**20

    assert times['cache_examples.ClassLevelSetup.track_example']['result'] == 500
    assert times['cache_examples.ClassLevelSetup.track_example2']['result'] == 500

    assert times['cache_examples.track_cache_foo']['result'] == 42
    assert times['cache_examples.track_cache_bar']['result'] == 12
    assert times['cache_examples.track_my_cache_foo']['result'] == 0

    assert times['cache_examples.ClassLevelSetupFail.track_fail']['result'] == None
    assert 'raise RuntimeError()' in times['cache_examples.ClassLevelSetupFail.track_fail']['stderr']

    profile_path = join(tmpdir, 'test.profile')
    with open(profile_path, 'wb') as fd:
        fd.write(times['time_secondary.track_value']['profile'])
    pstats.Stats(profile_path)

    # Check for running setup on each repeat (one extra run from profile)
    # The output would contain error messages if the asserts in the benchmark fail.
    expected = ["<%d>" % j for j in range(1, 12)]
    assert times['time_examples.TimeWithRepeat.time_it']['stderr'].split() == expected

    # Calibration of iterations should not rerun setup
    expected = ['setup']*2
    assert times['time_examples.TimeWithRepeatCalibrate.time_it']['stderr'].split() == expected


def test_invalid_benchmark_tree(tmpdir):
    tmpdir = six.text_type(tmpdir)
    os.chdir(tmpdir)

    d = {}
    d.update(ASV_CONF_JSON)
    d['benchmark_dir'] = INVALID_BENCHMARK_DIR
    d['env_dir'] = "env"
    d['repo'] = tools.generate_test_repo(tmpdir, [0]).path
    conf = config.Config.from_json(d)

    envs = list(environment.get_environments(conf, None))

    with pytest.raises(util.UserError):
        b = benchmarks.Benchmarks(conf, envs)


def test_table_formatting():
    benchmark = {'params': [], 'param_names': [], 'unit': 's'}
    result = []
    expected = ["[]"]
    assert benchmarks._format_benchmark_result(result, benchmark) == expected

    benchmark = {'params': [['a', 'b', 'c']], 'param_names': ['param1'], "unit": "seconds"}
    result = [1e-6, 2e-6, 3e-6]
    expected = ("======== ========\n"
                " param1          \n"
                "-------- --------\n"
                "   a      1.00\u03bcs \n"
                "   b      2.00\u03bcs \n"
                "   c      3.00\u03bcs \n"
                "======== ========")
    table = "\n".join(benchmarks._format_benchmark_result(result, benchmark, max_width=80))
    assert table == expected

    benchmark = {'params': [["'a'", "'b'", "'c'"], ["[1]", "[2]"]], 'param_names': ['param1', 'param2'], "unit": "seconds"}
    result = [1, 2, None, 4, 5, float('nan')]
    expected = ("======== ======== =======\n"
                "--            param2     \n"
                "-------- ----------------\n"
                " param1    [1]      [2]  \n"
                "======== ======== =======\n"
                "   a      1.00s    2.00s \n"
                "   b      failed   4.00s \n"
                "   c      5.00s     n/a  \n"
                "======== ======== =======")
    table = "\n".join(benchmarks._format_benchmark_result(result, benchmark, max_width=80))
    assert table == expected

    expected = ("======== ======== ========\n"
                " param1   param2          \n"
                "-------- -------- --------\n"
                "   a       [1]     1.00s  \n"
                "   a       [2]     2.00s  \n"
                "   b       [1]     failed \n"
                "   b       [2]     4.00s  \n"
                "   c       [1]     5.00s  \n"
                "   c       [2]      n/a   \n"
                "======== ======== ========")
    table = "\n".join(benchmarks._format_benchmark_result(result, benchmark, max_width=0))
    assert table == expected


def test_find_benchmarks_cwd_imports(tmpdir):
    # Test that files in the directory above the benchmark suite are
    # not importable

    tmpdir = six.text_type(tmpdir)
    os.chdir(tmpdir)

    os.makedirs('benchmark')
    with open(os.path.join('benchmark', '__init__.py'), 'w') as f:
        pass

    with open(os.path.join('benchmark', 'test.py'), 'w') as f:
        f.write("""
try:
    import this_should_really_not_be_here
    raise AssertionError('This should not happen!')
except ImportError:
    pass

def track_this():
    return 0
""")

    with open(os.path.join('this_should_really_not_be_here.py'), 'w') as f:
        f.write("raise AssertionError('Should not be imported!')")

    d = {}
    d.update(ASV_CONF_JSON)
    d['env_dir'] = "env"
    d['benchmark_dir'] = 'benchmark'
    d['repo'] = tools.generate_test_repo(tmpdir, [0]).path
    conf = config.Config.from_json(d)

    envs = list(environment.get_environments(conf, None))

    b = benchmarks.Benchmarks(conf, envs, regex='track_this')
    assert len(b) == 1
