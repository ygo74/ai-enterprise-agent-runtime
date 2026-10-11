"""Operator configuration, not delivered as part of the agent's integration glue."""

import os

from ygo74.agent_runtime.domains.auth.apikey_authenticator import (
    StaticApiKeyUserResolver,
)
from ygo74.agent_runtime.domains.auth.auth_context import ResolvedUser
from ygo74.agent_runtime.domains.auth.authentication_policy import AuthenticationPolicy
from ygo74.agent_runtime.domains.discovery.discovery_configuration import (
    DiscoveryConfiguration,
)
from ygo74.agent_runtime.domains.endpoints.managed_worker import WorkerSettings

key = os.environ["NATIVE_WORKER_API_KEY"]
settings = WorkerSettings(
    deployment_id="native-echo-local",
    identity_namespace="local-reference",
    authentication=AuthenticationPolicy.api_key(StaticApiKeyUserResolver({
        key: ResolvedUser(user_id="local-developer", name="Local developer"),
    })),
    discovery=DiscoveryConfiguration(enable_openai_models=True, require_authentication=True),
)
