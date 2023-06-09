from __future__ import annotations
from dataclasses import dataclass
import json
from typing import Dict, List, Optional
from robot.api.logger import trace
from CapabilitiesLibrary import CapabilitiesLibrary
from confd_gnmi_common import _make_string_path, datatype_str_to_int, \
    encoding_str_to_int, make_gnmi_path, split_gnmi_path


@dataclass
class GetRequestParameters:
    """ Placeholder for all the parameters of GetRequest.\n
        Its contents to be state-fully set by the calls to `set_..._to()` methods. """
    prefix: str = None
    paths: List[str] = None
    type: int = 0  # TODO - which one to use?
    encoding: int = None
    use_models: List[dict] = None

    def to_kwargs(self, default_encoding: Optional[int], default_path: Optional[str]):
        if self.paths is not None:
            paths = self.paths
        else:
            paths = [default_path] if default_path is not None else []
        if self.encoding is not None:
            encoding = self.encoding
        else:
            encoding = default_encoding if default_encoding is not None else None
        return {
            'prefix': self.prefix,
            'paths': paths,
            'get_type': self.type,
            'encoding': encoding
        }


@dataclass
class UpdatePayload:
    path: str
    value_type: str
    value: Dict[str, object]

    @staticmethod
    def from_obj(updateObj):
        path = _make_string_path(updateObj.path, xpath=True)
        # TODO - bug - fix for proper data types/encodings/values...
        (value_type, dict_data) = str(updateObj.val).split(': ', 1)
        value = json.loads(dict_data)
        if isinstance(value, str) and len(value) > 0:
            value = json.loads(value)
        return UpdatePayload(path=path, value_type=value_type, value=value)

    def is_empty(self):
        value_is_empty = not self.value
        return value_is_empty


class GetLibrary(CapabilitiesLibrary):
    """ ROBOT test suite library for servicing the gNMI GetRequest tests.\n
        Uses internal state to manage request parameters and response data. """
    ROBOT_LIBRARY_SCOPE = 'SUITE'

    default_encoding: Optional[int]
    default_path: Optional[str]
    params: GetRequestParameters

    def __init__(self, lib_config) -> None:
        super().__init__(lib_config)
        config_encoding = lib_config.default_encoding
        self.default_encoding = encoding_str_to_int(config_encoding) \
                                    if config_encoding is not None else None
        self.default_path = lib_config.default_path or None
        self.params = GetRequestParameters()

    def get_last_updates_count(self):
        """ Return total number of updates in last response payload,
            or 0 if none OK response has been received. """
        if self.last_response is None:
            return 0
        # trace(self.last_response)
        return sum(len(n.update) for n in self.last_response.notification)

    def supported_models_should_include(self, model_name: str) -> bool:
        # TODO - rewrite to more efficient any()...
        models = self.get_supported_model_names()
        assert model_name in models, f'CapabilityResponse does NOT include \"{model_name}\"'

    def get_supported_model_names(self):
        """ Return list of all the models supported by device/server.\n
            This is retrieved from the `CapabilityRequest`'s supported_models property. """
        response = self._client.get_capabilities()
        return [model.name for model in response.supported_models]

    def cleanup_getrequest_parameters(self):
        """ Clear all parameters of following `GetRequest` to be empty. """
        self.params = GetRequestParameters()

    def prefix_set_to(self, prefix: str):
        """ Set the `prefix` parameter of the next `GetRequest` to specified value. """
        self.params.prefix = prefix
        trace(f"next GetRequest prefix set to: {prefix}")

    def encoding_set_to(self, encoding: str):
        """ Set the `Encoding` parameter of the next `GetRequest` to specified value. """
        self.params.encoding = encoding_str_to_int(encoding, no_error=True)
        trace(f"next GetRequest encoding set to: {self.params.encoding} (input: {encoding})")

    def datatype_set_to(self, data_type: str):
        """ Set the `DataType` parameter of the next `GetRequest` to specified value. """
        self.params.type = datatype_str_to_int(data_type, no_error=True)
        trace(f"next GetRequest datatype set to: {self.params.type} (input: {data_type})")

    def paths_include(self, path: str):
        """ Add a path parameter into collected array for next `GetRequest`. """
        params = self.params
        if params.paths is None:
            params.paths = []
        params.paths.append(path)
        trace(f"next GetRequest paths extended with: {path}")

    def dispatch_get_request(self):
        """ Dispatch the GetRequest towards server and store the received response.\n
            Parameters of the request are set according to previously set values. """
        self.cleanup_last_request_results()
        try:
            kwargs = self.params.to_kwargs(self.default_encoding, self.default_path)
            trace(f"Dispatching GetRequest with parameters: {kwargs}")
            self.last_response = self._client.get_public(**kwargs)
        except Exception as ex:
            self.last_exception = ex
        trace(f"Last exception: {self.last_exception}")
        trace(f"Last response: {self.last_response}")

    def get_last_flattened_updates(self) -> List[List[UpdatePayload]]:
        if self.last_response is None:
            return None
        notifications = self.last_response.notification
        updates = []
        for n in notifications:
            for update in n.update:
                updates.append(UpdatePayload.from_obj(update))
        trace(f"Last updates: {str(updates)}")
        return updates

    def _updates_include(self, text: str) -> bool:
        updates = self.get_last_flattened_updates()
        if updates is None:
            return False
        for update in updates:
            if update.is_empty():
                continue
            if isinstance(update.value, dict) and text in update.value:
                return True
            if update.path.endswith(text):
                return True
        return False

    def check_last_updates_include(self, text: str) -> bool:
        assert self._updates_include(text), f"Expected \"{text}\" not found in any of updates!"

    def check_last_updates_not_include(self, text: str) -> bool:
        assert not self._updates_include(text), f"Unexpected \"{text}\" found in some of updates!"

    def _last_updates_not_empty(self) -> bool:
        last_updates = self.get_last_flattened_updates()
        return any(not update.is_empty() for update in last_updates)

    def check_last_updates_not_empty(self) -> bool:
        """ Verify that last updates are not empty, and include some data. """
        non_empty_contents = self._last_updates_not_empty()
        assert non_empty_contents, "No updates with payload from last request!"

    def should_not_receive_data_response(self):
        """ Verify that last request ended either with negative response from server,
            or with ok response containing no data. """
        got_error = self.last_response is None and self.last_exception is not None
        got_empty = not self._last_updates_not_empty()
        message = 'Didn\'t receive expected empty or error response'
        self._assert_condition(got_error or got_empty, message)

    def test_teardown(self):
        super().test_teardown()
        self.cleanup_getrequest_parameters()

    def get_projections_from_key_dictionary(self, key_dictionary: Dict[str, str]) -> str:
        """ Helper method to convert a dictionary of list-entry key mappings
            into XPath like string portion, e.g.:
                { "name": "eth0"} --> [name=eth0]
                { "name": "eth0", "type": "ethernet" } --> [name=eth0][type=ethernet]
          """
        projections = [f"[{name}={value}]" for [name, value] in key_dictionary.items()]
        return "".join(projections)

    @staticmethod
    def count_prefix_path_steps(full_path: str):
        """ Return number of nodes (separated with \'/\') on the specified path string. """
        elem_path = make_gnmi_path(full_path)
        return len(elem_path.elem) - 1

    @staticmethod
    def split_prefix_path(xpath_path: str, step: int):
        """ Split the input path at specified index/slash position,
            and return the two parts - leading \"prefix\" and the rest, \"path\". """
        (prefix, path) = split_gnmi_path(xpath_path, step)
        return (prefix, path)
