# python3
# Copyright 2021 InstaDeep Ltd. All rights reserved.
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

"""Example running MADQN on the pettingzoo environment."""

import functools
from datetime import datetime
from typing import Any, Mapping

import launchpad as lp
import sonnet as snt
import tensorflow as tf
from absl import app, flags
from acme import types
from acme.tf.networks import DQNAtariNetwork

from mava import specs as mava_specs
from mava.components.tf.networks import epsilon_greedy_action_selector
from mava.systems.tf import madqn
from mava.utils import lp_utils
from mava.utils.environments import pettingzoo_utils

FLAGS = flags.FLAGS

flags.DEFINE_string(
    "env_class",
    "atari",
    "Pettingzoo environment class, e.g. atari (str).",
)

flags.DEFINE_string(
    "env_name",
    "maze_craze_v2",
    "Pettingzoo environment name, e.g. pong (str).",
)
flags.DEFINE_string(
    "mava_id",
    str(datetime.now()),
    "Experiment identifier that can be used to continue experiments.",
)
flags.DEFINE_string("base_dir", "~/mava/", "Base dir to store experiments.")


def make_networks(
    environment_spec: mava_specs.MAEnvironmentSpec,
    epsilon: tf.Variable = tf.Variable(0.05, trainable=False),
    shared_weights: bool = True,
) -> Mapping[str, types.TensorTransformation]:
    """Creates networks used by the agents."""

    specs = environment_spec.get_agent_specs()

    # Create agent_type specs
    if shared_weights:
        type_specs = {key.split("_")[0]: specs[key] for key in specs.keys()}
        specs = type_specs

    def action_selector_fn(
        q_values: types.NestedTensor, legal_actions: types.NestedTensor
    ) -> types.NestedTensor:
        return epsilon_greedy_action_selector(
            action_values=q_values, legal_actions_mask=legal_actions
        )

    q_networks = {}
    action_selectors = {}
    for key in specs.keys():

        # Get total number of action dimensions from action spec.
        num_dimensions = specs[key].actions.num_values

        # Create the q-value network.
        q_network = DQNAtariNetwork(num_dimensions)

        # epsilon greedy action selector
        action_selector = action_selector_fn

        q_networks[key] = q_network
        action_selectors[key] = action_selector

    return {
        "q_networks": q_networks,
        "action_selectors": action_selectors,
    }


def main(_: Any) -> None:

    # set loggers info
    log_info = (FLAGS.base_dir, f"{FLAGS.mava_id}/logs")

    environment_factory = functools.partial(
        pettingzoo_utils.make_environment,
        env_class=FLAGS.env_class,
        env_name=FLAGS.env_name,
    )

    network_factory = lp_utils.partial_kwargs(make_networks)

    # Checkpointer appends "Checkpoints" to checkpoint_dir
    checkpoint_dir = f"{FLAGS.base_dir}/{FLAGS.mava_id}"
    program = madqn.MADQN(
        environment_factory=environment_factory,
        network_factory=network_factory,
        num_executors=2,
        log_info=log_info,
        policy_optimizer=snt.optimizers.Adam(learning_rate=1e-3),
        checkpoint_subpath=checkpoint_dir,
    ).build()

    lp.launch(program, lp.LaunchType.LOCAL_MULTI_PROCESSING)


if __name__ == "__main__":
    app.run(main)
