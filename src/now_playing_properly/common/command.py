from enum import Enum
from . import command_params
from . import command_responses
from .command_params import BaseParams
from .command_responses import BaseResponse


class Commands(Enum):
    GET_ALIAS = 1
    SET_ALIAS = 2
    REMOVE_ALIAS = 3
    DISCONNECT = 4
    PLAY = 5
    PAUSE = 6
    STOP = 7
    PLAYPAUSE = 8
    GET_STATUS = 9
    OPEN_URI = 10
    SEEK = 11


param_classes: dict[Commands, BaseParams] = {
    Commands.GET_ALIAS: None,
    Commands.SET_ALIAS: command_params.SetAliasParams,
    Commands.REMOVE_ALIAS: None,
    Commands.DISCONNECT: None,
    Commands.PLAY: command_params.PlayerControlParams,
    Commands.PAUSE: command_params.PlayerControlParams,
    Commands.STOP: command_params.PlayerControlParams,
    Commands.PLAYPAUSE: command_params.PlayerControlParams,
    Commands.GET_STATUS: command_params.PlayerControlParams,
    Commands.OPEN_URI: command_params.OpenURIParams,
    Commands.SEEK: command_params.SeekParams,
}

response_classes: dict[Commands, BaseResponse] = {
    Commands.GET_ALIAS: command_responses.GetAliasResponse,
    Commands.SET_ALIAS: command_responses.BaseResponse,
    Commands.REMOVE_ALIAS: command_responses.BaseResponse,
    Commands.DISCONNECT: None,
    Commands.PLAY: command_responses.BaseResponse,
    Commands.PAUSE: command_responses.BaseResponse,
    Commands.STOP: command_responses.BaseResponse,
    Commands.PLAYPAUSE: command_responses.BaseResponse,
    Commands.GET_STATUS: command_responses.GetStatusResponse,
    Commands.OPEN_URI: command_responses.BaseResponse,
    Commands.SEEK: command_responses.BaseResponse,
}
