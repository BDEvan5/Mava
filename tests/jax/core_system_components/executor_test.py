# python3
# Copyright 2022 InstaDeep Ltd. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Tests for executor class for Jax-based Mava systems."""
from types import SimpleNamespace
from typing import List

import dm_env
import numpy as np
import pytest

from mava.callbacks import Callback
from mava.systems.jax import Executor
from tests.jax.hook_order_tracking import HookOrderTracking


class TestExecutor(HookOrderTracking, Executor):
    def __init__(
        self,
        store: SimpleNamespace,
        components: List[Callback],
    ) -> None:
        """Initialise the parameter server."""
        self.reset_hook_list()

        super().__init__(store, components)


@pytest.fixture
def test_executor() -> Executor:
    """Dummy Executor with no components."""
    return TestExecutor(
        store=SimpleNamespace(
            store_key="expected_value",
            is_evaluator=False,
        ),
        components=[],
    )


def test_store_loaded(test_executor: Executor) -> None:
    """Test that store is loaded during init."""
    assert test_executor.store.store_key == "expected_value"
    assert not test_executor.store.is_evaluator
    assert test_executor._evaluator == test_executor.store.is_evaluator


def test_observe_first_store(test_executor: Executor) -> None:
    """Test that store is handled properly in observe_first"""
    timestep = dm_env.TimeStep(
        step_type="type1", reward=-100, discount=0.9, observation=np.array([1, 2, 3])
    )
    extras = {"extras_key": "extras_value"}
    test_executor.observe_first(
        timestep=timestep, extras={"extras_key": "extras_value"}
    )
    assert test_executor.store.timestep == timestep
    assert test_executor.store.extras == extras
