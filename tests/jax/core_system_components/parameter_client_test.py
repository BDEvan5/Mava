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

"""Tests for parameter client class for Jax-based Mava systems"""

from types import SimpleNamespace
from typing import Any, Dict, List, Sequence, Set, Union

import numpy as np
import pytest

from mava.callbacks.base import Callback
from mava.systems.jax.parameter_client import ParameterClient
from mava.systems.jax.parameter_server import ParameterServer


class MockParameterServer(ParameterServer):
    def __init__(
        self,
        store: SimpleNamespace,
        components: List[Callback],
        set_parameter_keys: Union[str, Sequence[str]],
    ) -> None:
        """Initialize mock parameter server."""
        self.store = store
        self.callbacks = components
        self.set_parameter_keys = set_parameter_keys

    def _increment_parameters(self, names: Union[str, Sequence[str], Set[str]]) -> None:
        """Dummy method to update get parameters before updating client"""
        for name in names:
            if name.split("_")[0] == "key":
                self.store.parameters[name] += 1
            elif name.split("-")[0] == "networks":
                self.store.parameters[name]["layer_0"]["weights"] += 1
                self.store.parameters[name]["layer_0"]["biases"] += 1

    def get_parameters(self, names: Union[str, Sequence[str]]) -> Any:
        """Dummy method for returning get parameters"""
        self.store._param_names = names

        # Manually increment all parameters except the set parameters
        # and add them to store to simulate parameters that have changed.
        get_names = set(names) - set(self.set_parameter_keys)
        self._increment_parameters(names=get_names)
        get_params = {name: self.store.parameters[name] for name in names}
        self.store.get_parameters = get_params

        return self.store.get_parameters

    def set_parameters(self, set_params: Dict[str, Any]) -> None:
        """Overwrite set parameters method"""

        self.store._set_params = set_params

        for key in set_params:
            self.store.parameters[key] = set_params[key]


@pytest.fixture
def mock_parameter_server() -> ParameterServer:
    """Create mock parameter server"""
    param_server = MockParameterServer(
        store=SimpleNamespace(
            parameters={
                "key_0": np.array(0, dtype=np.int32),
                "key_1": np.array(1, dtype=np.float32),
                "key_2": np.array(2, dtype=np.int32),
                "key_3": np.array(3, dtype=np.int32),
                "key_4": np.array(4, dtype=np.int32),
                "networks-network_key_0": {"layer_0": {"weights": 0, "biases": 0}},
                "networks-network_key_1": {"layer_0": {"weights": 1, "biases": 1}},
                "networks-network_key_2": {"layer_0": {"weights": 2, "biases": 2}},
            },
        ),
        components=[],
        set_parameter_keys=["key_0", "key_2"],
    )

    return param_server


@pytest.fixture()
def parameter_client(mock_parameter_server: ParameterServer) -> ParameterClient:
    """Creates a mock parameter client for testing

    Args:
        mock_parameter_server: ParameterServer

    Returns:
        A parameter client object.
    """

    param_client = ParameterClient(
        client=mock_parameter_server,
        parameters={
            "key_0": np.array(0, dtype=np.int32),
            "key_1": np.array(1, dtype=np.float32),
            "key_2": np.array(2, dtype=np.int32),
            "key_3": np.array(3, dtype=np.int32),
            "key_4": np.array(4, dtype=np.int32),
            "networks-network_key_0": {"layer_0": {"weights": 0, "biases": 0}},
            "networks-network_key_1": {"layer_0": {"weights": 1, "biases": 1}},
            "networks-network_key_2": {"layer_0": {"weights": 2, "biases": 2}},
        },
        get_keys=[
            "key_0",
            "key_1",
            "key_2",
            "key_3",
            "key_4",
            "networks-network_key_0",
            "networks-network_key_1",
            "networks-network_key_2",
        ],
        set_keys=[
            "key_0",
            "key_2",
        ],
        update_period=10,
    )

    return param_client


def test_add_and_wait(parameter_client: ParameterClient) -> None:
    """Test add and wait method."""
    parameter_client.add_and_wait(params={"new_key": "new_value"})

    assert parameter_client._client.store._add_to_params == {"new_key": "new_value"}


def test_get_and_wait(parameter_client: ParameterClient) -> None:
    """Test get and wait method."""
    parameter_client.get_and_wait()
    # check that all parameters have been incremented and updated
    # except for the set parameters
    assert parameter_client._parameters == {
        "key_0": np.array(0, dtype=np.int32),
        "key_1": np.array(2, dtype=np.float32),
        "key_2": np.array(2, dtype=np.int32),
        "key_3": np.array(4, dtype=np.int32),
        "key_4": np.array(5, dtype=np.int32),
        "networks-network_key_0": {"layer_0": {"weights": 1, "biases": 1}},
        "networks-network_key_1": {"layer_0": {"weights": 2, "biases": 2}},
        "networks-network_key_2": {"layer_0": {"weights": 3, "biases": 3}},
    }


def test_get_all_and_wait(parameter_client: ParameterClient) -> None:
    """Test get all and wait method."""
    parameter_client.get_all_and_wait()
    # check that all parameters have been incremented and updated
    # except for the set parameters
    assert parameter_client._parameters == {
        "key_0": np.array(0, dtype=np.int32),
        "key_1": np.array(2, dtype=np.float32),
        "key_2": np.array(2, dtype=np.int32),
        "key_3": np.array(4, dtype=np.int32),
        "key_4": np.array(5, dtype=np.int32),
        "networks-network_key_0": {"layer_0": {"weights": 1, "biases": 1}},
        "networks-network_key_1": {"layer_0": {"weights": 2, "biases": 2}},
        "networks-network_key_2": {"layer_0": {"weights": 3, "biases": 3}},
    }


def test_set_and_wait(parameter_client: ParameterClient) -> None:
    """Test set and wait method."""
    pass


def test__copy(parameter_client: ParameterClient) -> None:
    """Test _copy method with different kinds of new parameters"""
    parameter_client._copy(
        new_parameters={
            "networks-network_key_0": {
                "layer_0": {"weights": "new_weights", "biases": "new_biases"}
            },
            "key_2": np.array(20, dtype=np.int32),
            "key_4": np.array([40], dtype=np.int32),
        }
    )

    assert parameter_client._parameters["networks-network_key_0"] == {
        "layer_0": {"weights": "new_weights", "biases": "new_biases"}
    }
    assert parameter_client._parameters["key_2"] == 20
    assert parameter_client._parameters["key_4"] == 40


def test__copy_not_implemented_error(parameter_client: ParameterClient) -> None:
    """Test that NotImplementedError is raised when a new parameter of the wrong \
        type is passed in."""

    with pytest.raises(NotImplementedError):
        parameter_client._copy(
            new_parameters={"wrong_type_parameter": lambda: "wrong_type"}
        )


def test__adjust_and_request(parameter_client: ParameterClient) -> None:
    """Test adjust and request method"""
    parameter_client._adjust_and_request()
