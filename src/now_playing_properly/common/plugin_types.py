import inspect
from pydantic import BaseModel
from dataclasses import dataclass
from httpx import AsyncClient, Client
from .metadata_spec import AudioMetadata, AudioMetadata
from typing import Dict, Any, Callable, Awaitable, Union, Type, Optional


class PluginState:
    pass


@dataclass
class PluginResponse:
    modified_keys: Optional[AudioMetadata]
    added_keys: Optional[Dict[str, Any]]


class BasePluginConfig(BaseModel):
    priority: int = 0
    enabled: bool = True


class BadDomainError(PermissionError):
    pass


@dataclass
class Resources:
    network_async: AsyncClient
    network_sync: Client


REQUIRED = ("name", "Config", "activation", "plugin_function")
STATE = ("State", "create_state")
NAME = __name__


class Plugin:
    name: str
    State: Optional[Type[PluginState]]
    create_state: Optional[Callable[[], PluginState]]
    Config: Type[BasePluginConfig]
    activation: Callable[[Optional[PluginState], BasePluginConfig, AudioMetadata], bool]
    plugin_function: Callable[
        [Optional[PluginState], BasePluginConfig, Resources, AudioMetadata],
        Union[Awaitable[PluginResponse], PluginResponse],
    ]

    def __init__(
        self,
        name: str = None,
        State: Optional[Type[PluginState]] = None,
        create_state: Optional[Callable[[], PluginState]] = None,
        Config: Type[BasePluginConfig] = None,
        activation: Callable[
            [Optional[PluginState], BasePluginConfig, AudioMetadata], bool
        ] = None,
        plugin_function: Callable[
            [Optional[PluginState], BasePluginConfig, Resources, AudioMetadata],
            Union[Awaitable[PluginResponse], PluginResponse],
        ] = None,
    ):
        # Fallback to class-level attributes if not provided in __init__
        self.name = name if name is not None else getattr(self, "name", None)
        self.State = State if State is not None else getattr(self, "State", None)
        self.create_state = (
            create_state
            if create_state is not None
            else getattr(self, "create_state", None)
        )
        self.Config = Config if Config is not None else getattr(self, "Config", None)
        self.activation = (
            activation if activation is not None else getattr(self, "activation", None)
        )
        self.plugin_function = (
            plugin_function
            if plugin_function is not None
            else getattr(self, "plugin_function", None)
        )

        # Deep strict validation
        self._validate_attributes()

    def _validate_attributes(self):
        # 1. Validate strictly required properties exist
        missing = [attr for attr in REQUIRED if getattr(self, attr, None) is None]
        if missing:
            raise TypeError(f"Missing required plugin attributes: {', '.join(missing)}")

        # 2. Validate Standard Types
        if not isinstance(self.name, str):
            raise TypeError(f"'name' must be a string, got {type(self.name).__name__}")

        if not isinstance(self.Config, type):
            raise TypeError(
                f"'Config' must be a class (type), got {type(self.Config).__name__}"
            )

        if self.State is not None and not isinstance(self.State, type):
            raise TypeError(
                f"'State' must be a class (type) or None, got {type(self.State).__name__}"
            )

        # 3. Validate Callables and their signatures
        if self.create_state is not None:
            self._validate_callable_signature(
                "create_state", self.create_state, expected_params_count=0
            )

        # activation and plugin_function both expect exactly 3 structural parameters (excluding self)
        self._validate_callable_signature(
            "activation", self.activation, expected_params_count=3
        )
        self._validate_callable_signature(
            "plugin_function", self.plugin_function, expected_params_count=4
        )

    def _validate_callable_signature(
        self, attr_name: str, obj: Any, expected_params_count: int
    ):
        # Verify it is actually callable (handles functions, lambdas, methods, and __call__ objects)
        if not callable(obj):
            raise TypeError(
                f"'{attr_name}' must be a callable object, got {type(obj).__name__}"
            )

        try:
            signature = inspect.signature(obj)
        except (ValueError, TypeError):
            # Fallback for built-ins or edge cases where signature cannot be extracted
            return

        # Filter out 'self' or 'cls' parameters if it's a bound method or an object with __call__
        params = list(signature.parameters.values())

        # If it's a regular method defined on a class that hasn't been bound yet
        # (or an instance method being analyzed during __init__ execution)
        if params and params[0].name in ("self", "cls"):
            # If it's an explicitly bound method, inspect automatically strips 'self'.
            # If it's passed as an unbound function from a subclass definition, 'self' is visible.
            params = params[1:]

        actual_count = len(params)
        if actual_count != expected_params_count:
            raise TypeError(
                f"'{attr_name}' has an invalid signature. "
                f"Expected {expected_params_count} parameters, but found {actual_count} "
                f"({', '.join(p.name for p in params)})."
            )


@dataclass
class UnixFD:
    """
    small helper class, when a plugin wants to return a unixfd in its custom data, wrap the file descriptor integer in this class so later marshalling can understand it
    """

    fd: int
