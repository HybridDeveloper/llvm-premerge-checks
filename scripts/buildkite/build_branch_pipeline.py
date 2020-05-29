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

import os
import yaml

if __name__ == '__main__':
    script_branch = os.getenv("scripts_branch", "master")
    queue = os.getenv("BUILDKITE_AGENT_META_DATA_QUEUE", "default")
    diff_id = os.getenv("ph_buildable_diff", "")
    steps = []
    linux_buld_step = {
        'label': 'build linux',
        'key': 'build-linux',
        'commands': [
            'export SRC=${BUILDKITE_BUILD_PATH}/llvm-premerge-checks',
            'rm -rf ${SRC}',
            'git clone --depth 1 --branch ${scripts_branch} https://github.com/google/llvm-premerge-checks.git ${SRC}',
            '${SRC}/scripts/phabtalk/add_url_artifact.py '
            '--phid="$ph_target_phid" '
            '--url="$BUILDKITE_BUILD_URL" '
            '--name="Buildkite build"',
            '${SRC}/scripts/premerge_checks.py --check-clang-format --check-clang-tidy',
            'exit 1',
        ],
        'artifact_paths': ['artifacts/**/*'],
        'agents': {'queue': queue, 'os': 'linux'}
    }
    windows_buld_step = {
        'label': 'build windows',
        'key': 'build-windows',
        'commands': [
            'set SRC=%BUILDKITE_BUILD_PATH%/llvm-premerge-checks',
            'rm -rf %SRC%',
            'git clone --depth 1 --branch %scripts_branch% https://github.com/google/llvm-premerge-checks.git %SRC%',
            '%SRC%/scripts/premerge_checks.py',
        ],
        'artifact_paths': ['artifacts/**/*'],
        'agents': {'queue': 'dev', 'os': 'windows'}
    }
    steps.append(linux_buld_step)
    # steps.append(windows_buld_step)
    report_step = {
        'label': 'report',
        'depends_on': [linux_buld_step['key']],
        'commands': [
            'echo report',
        ],
        'allow_dependency_failure': True,
        'artifact_paths': ['artifacts/**/*'],
        'agents': {'queue': queue, 'os': 'linux'}
    }
    steps.append(report_step)
    print(yaml.dump({'steps': steps}))
