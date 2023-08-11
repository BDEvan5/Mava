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

from typing import NamedTuple, Tuple

import chex
import jax.numpy as jnp
from flax import struct
from jumanji import specs
from jumanji.environments.routing.robot_warehouse import Observation, State
from jumanji.types import TimeStep
from jumanji.wrappers import Wrapper


class ObservationGlobalState(NamedTuple):
    """The observation that the agent sees.
    agents_view: the agents' view of other agents and shelves within their
        sensor range. The number of features in the observation array
        depends on the sensor range of the agent.
    action_mask: boolean array specifying, for each agent, which action
        (up, right, down, left) is legal.
    global_state: the global state of the environment, which is the
        concatenation of the agents' views.
    step_count: the number of steps elapsed since the beginning of the episode.
    """

    agents_view: chex.Array  # (num_agents, num_obs_features)
    action_mask: chex.Array  # (num_agents, 5)
    global_state: chex.Array  # (num_agents * num_obs_features, )
    step_count: chex.Array  # (num_agents, )


@struct.dataclass
class LogEnvState:
    """State of the `LogWrapper`."""

    env_state: State
    episode_returns: chex.Numeric
    episode_lengths: chex.Numeric
    # Information about the episode return and length for logging purposes.
    episode_return_info: chex.Numeric
    episode_length_info: chex.Numeric


class LogWrapper(Wrapper):
    """Log the episode returns and lengths."""

    def reset(self, key: chex.PRNGKey) -> Tuple[LogEnvState, TimeStep]:
        """Reset the environment."""
        state, timestep = self._env.reset(key)
        state = LogEnvState(state, jnp.float32(0.0), 0, jnp.float32(0.0), 0)
        return state, timestep

    def step(
        self,
        state: State,
        action: jnp.ndarray,
    ) -> Tuple[State, TimeStep]:
        """Step the environment."""
        env_state, timestep = self._env.step(state.env_state, action)

        done = timestep.last()
        not_done = 1 - done

        new_episode_return = state.episode_returns + jnp.mean(timestep.reward)
        new_episode_length = state.episode_lengths + 1
        episode_return_info = state.episode_return_info * not_done + new_episode_return * done
        episode_length_info = state.episode_length_info * not_done + new_episode_length * done

        state = LogEnvState(
            env_state=env_state,
            episode_returns=new_episode_return * not_done,
            episode_lengths=new_episode_length * not_done,
            episode_return_info=episode_return_info,
            episode_length_info=episode_length_info,
        )
        return state, timestep


class RwareMultiAgentWrapper(Wrapper):
    """Multi-agent wrapper for the Robotic Warehouse environment."""

    def reset(self, key: chex.PRNGKey) -> Tuple[State, TimeStep]:
        """Reset the environment. Updates the step count."""
        state, timestep = self._env.reset(key)
        timestep.observation = Observation(
            agents_view=timestep.observation.agents_view,
            action_mask=timestep.observation.action_mask,
            step_count=jnp.repeat(timestep.observation.step_count, self._env.num_agents),
        )
        return state, timestep

    def step(self, state: State, action: jnp.ndarray) -> Tuple[State, TimeStep]:
        """Step the environment. Updates the step count."""
        state, timestep = self._env.step(state, action)
        timestep.observation = Observation(
            agents_view=timestep.observation.agents_view,
            action_mask=timestep.observation.action_mask,
            step_count=jnp.repeat(timestep.observation.step_count, self._env.num_agents),
        )
        return state, timestep

    def observation_spec(self) -> specs.Spec[Observation]:
        """Specification of the observation of the `RobotWarehouse` environment."""
        step_count = specs.BoundedArray(
            (self._env.num_agents,),
            jnp.int32,
            [0] * self._env.num_agents,
            [self._env.time_limit] * self._env.num_agents,
            "step_count",
        )
        return self._env.observation_spec().replace(step_count=step_count)


class RwareMultiAgentWithGlobalStateWrapper(Wrapper):
    """Multi-agent wrapper for the Robotic Warehouse environment.

    The wrapper includes a global environment state to be used by the centralised critic.
    Note here that since robotic warehouse does not have a global state, we create one by concatenating
    the observations of all agents.
    """

    def reset(self, key: chex.PRNGKey) -> Tuple[State, TimeStep]:
        """Reset the environment. Updates the step count."""
        state, timestep = self._env.reset(key)
        global_state = jnp.concatenate(timestep.observation.agents_view, axis=0)
        timestep.observation = ObservationGlobalState(
            agents_view=timestep.observation.agents_view,
            action_mask=timestep.observation.action_mask,
            global_state=global_state,
            step_count=jnp.repeat(
                timestep.observation.step_count, self._env.num_agents
            ),
        )
        return state, timestep

    def step(self, state: State, action: jnp.ndarray) -> Tuple[State, TimeStep]:
        """Step the environment. Updates the step count."""
        state, timestep = self._env.step(state, action)
        global_state = jnp.concatenate(timestep.observation.agents_view, axis=0)
        timestep.observation = ObservationGlobalState(
            agents_view=timestep.observation.agents_view,
            action_mask=timestep.observation.action_mask,
            global_state=global_state,
            step_count=jnp.repeat(
                timestep.observation.step_count, self._env.num_agents
            ),
        )
        return state, timestep

    def observation_spec(self) -> specs.Spec[Observation]:
        """Specification of the observation of the `RobotWarehouse` environment."""

        agents_view = specs.Array(
            (self._env.num_agents, self.num_obs_features), jnp.int32, "agents_view"
        )
        action_mask = specs.BoundedArray(
            (self._env.num_agents, 5), bool, False, True, "action_mask"
        )
        global_state = specs.Array(
            (self._env.num_agents * self.num_obs_features,), jnp.int32, "global_state"
        )
        step_count = specs.BoundedArray(
            (self._env.num_agents,),
            jnp.int32,
            [0] * self._env.num_agents,
            [self._env.time_limit] * self._env.num_agents,
            "step_count",
        )

        return specs.Spec(
            ObservationGlobalState,
            "ObservationSpec",
            agents_view=agents_view,
            action_mask=action_mask,
            global_state=global_state,
            step_count=step_count,
        )
