#!/usr/bin/env python3
# Copyright 2020 Google LLC
#
# Licensed under the the Apache License v2.0 with LLVM Exceptions (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://llvm.org/LICENSE.txt
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# Runs all check on buildkite agent.
import argparse
import json
import logging
import os
import pathlib
import re
import shutil
import subprocess
import time
import uuid
from typing import Callable, Optional
from buildkite.utils import upload_file, format_url

import clang_format_report
import clang_tidy_report
import run_cmake
import test_results_report
from phabtalk.phabtalk import Report, CheckResult, PhabTalk
from phabtalk.add_url_artifact import maybe_add_url_artifact


def add_shell_result(report: Report, name: str, exit_code: int) -> CheckResult:
    logging.info(f'"{name}" exited with {exit_code}')
    z = CheckResult.SUCCESS
    if exit_code != 0:
        z = CheckResult.FAILURE
    report.add_step(name, z, '')
    return z


def ninja_all_report(report: Report) -> CheckResult:
    print('Full will be available in Artifacts "ninja-all.log"')
    r = subprocess.run(f'ninja all | '
                       f'tee {artifacts_dir}/ninja-all.log | '
                       f'grep -vE "\\[.*] (Building|Linking|Copying|Generating|Creating)"',
                       shell=True, cwd=build_dir)
    return add_shell_result(report, 'ninja all', r.returncode)


def ninja_check_all_report(report: Report) -> CheckResult:
    # TODO: merge running ninja check all and analysing results in one step?
    print('Full will be available in Artifacts "ninja-check-all.log"')
    r = subprocess.run(f'ninja check-all | tee {artifacts_dir}/ninja-check-all.log | '
                       f'grep -vE "^\\[.*] (Building|Linking)" | '
                       f'grep -vE "^(PASS|XFAIL|UNSUPPORTED):"', shell=True, cwd=build_dir)
    z = add_shell_result(report, 'ninja check all', r.returncode)
    # TODO: check if test-results are present.
    report.add_artifact(build_dir, 'test-results.xml', 'test results')
    test_results_report.run(os.path.join(build_dir, 'test-results.xml'), report)
    return z


def run_step(name: str, report: Report, thunk: Callable[[Report], CheckResult]) -> CheckResult:
    global timings
    start = time.time()
    print(f'---  {name}')  # New section in Buildkite log.
    result = thunk(report)
    timings[name] = time.time() - start
    # Expand section if it failed.
    if result == CheckResult.FAILURE:
        print('^^^ +++')
    return result


def cmake_report(report: Report) -> CheckResult:
    global build_dir
    cmake_result, build_dir, cmake_artifacts = run_cmake.run('detect', os.getcwd())
    for file in cmake_artifacts:
        if os.path.exists(file):
            shutil.copy2(file, artifacts_dir)
    return add_shell_result(report, 'cmake', cmake_result)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Runs premerge checks8')
    parser.add_argument('--log-level', type=str, default='WARNING')
    parser.add_argument('--check-clang-format', action='store_true')
    parser.add_argument('--check-clang-tidy', action='store_true')
    args = parser.parse_args()
    logging.basicConfig(level=args.log_level, format='%(levelname)-7s %(message)s')
    build_dir = ''
    scripts_dir = pathlib.Path(__file__).parent.absolute()
    phabtalk = PhabTalk(os.getenv('CONDUIT_TOKEN'), 'https://reviews.llvm.org/api/', False)
    maybe_add_url_artifact(phabtalk, os.getenv('ph_target_phid'), os.getenv('BUILDKITE_BUILD_URL'), 'Buildkite build 2')
    artifacts_dir = os.path.join(os.getcwd(), 'artifacts')
    os.makedirs(artifacts_dir, exist_ok=True)
    with open(os.path.join(artifacts_dir, 'build_result.txt'), 'w') as f:
        f.write("failed")
    report = Report()
    timings = {}
    cmake_result = run_step('cmake', report, cmake_report)
    if cmake_result == CheckResult.SUCCESS:
        compile_result = run_step('ninja all', report, ninja_all_report)
        if compile_result == CheckResult.SUCCESS:
            run_step('ninja check all', report, ninja_check_all_report)
        if args.check_clang_tidy:
            run_step('clang-tidy', report,
                     lambda x: clang_tidy_report.run('HEAD~1', os.path.join(scripts_dir, 'clang-tidy.ignore'), x))
    if args.check_clang_format:
        run_step('clang-format', report,
                 lambda x: clang_format_report.run('HEAD~1', os.path.join(scripts_dir, 'clang-format.ignore'), x))
    print('+++ summary')
    print(f'Branch {os.getenv("BUILDKITE_BRANCH")} at {os.getenv("BUILDKITE_REPO")}')
    ph_buildable_diff = os.getenv('ph_buildable_diff')
    if ph_buildable_diff is not None:
        url = f'https://reviews.llvm.org/D{os.getenv("ph_buildable_revision")}?id={ph_buildable_diff}'
        print(f'Review: {format_url(url)}')
    if os.getenv('BUILDKITE_TRIGGERED_FROM_BUILD_NUMBER') is not None:
        url = f'https://buildkite.com/llvm-project/' \
              f'{os.getenv("BUILDKITE_TRIGGERED_FROM_BUILD_PIPELINE_SLUG")}/'\
              f'builds/{os.getenv("BUILDKITE_TRIGGERED_FROM_BUILD_NUMBER")}'
        print(f'Triggered from build {format_url(url)}')
    logging.debug(report)
    success = True
    for s in report.steps:
        mark = 'V'
        if s['result'] == CheckResult.UNKNOWN:
            mark = '?'
        if s['result'] == CheckResult.FAILURE:
            success = False
            mark = 'X'
        msg = s['message']
        if len(msg):
            msg = ': ' + msg
        print(f'{mark} {s["title"]}{msg}')

    # TODO: dump the report and deduplicate tests and other reports later (for multiple OS) in a separate step.
    ph_target_phid = os.getenv('ph_target_phid')
    if ph_target_phid is not None:
        phabtalk.update_build_status(ph_buildable_diff, ph_target_phid, True, success, report.lint, report.unit)
        for a in report.artifacts:
                url = upload_file(a['dir'], a['file'])
                if url is not None:
                    maybe_add_url_artifact(phabtalk, ph_target_phid, url, a['name'])
    else:
        logging.warning('No phabricator phid is specified. Will not update the build status in Phabricator')
    # TODO: add link to report issue on github
    with open(os.path.join(artifacts_dir, 'step_timings.json'), 'w') as f:
        f.write(json.dumps(timings))
    if success:
        with open(os.path.join(artifacts_dir, 'build_result.txt'), 'w') as f:
            f.write("succeeded")
    else:
        print('Build completed with failures')
        # TODO: test with python error in script
        exit(1)
