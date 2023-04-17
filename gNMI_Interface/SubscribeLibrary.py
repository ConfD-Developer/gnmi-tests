from __future__ import annotations

import typing as t
import threading
import queue
from datetime import datetime as dt

from confd_gnmi_common import make_gnmi_path, encoding_str_to_int
from confd_gnmi_client import ConfDgNMIClient
from CapabilitiesLibrary import CapabilitiesLibrary
from gnmi_config import GNMIConfigTree, apply_response, UpdateType

import grpc
import gnmi_pb2 as gnmi

SlistType = t.Optional[t.Union[gnmi.Poll, gnmi.SubscriptionList]]


NO_SYNC_RESPONSE = 'The server did not send sync_response'


class Requester(threading.Thread):
    def __init__(self, client: ConfDgNMIClient) -> None:
        super().__init__()
        self.client: ConfDgNMIClient = client
        self._slist_queue: queue.Queue[SlistType] = queue.Queue()
        self._response_queue: queue.Queue[gnmi.SubscribeResponse] = queue.Queue()
        self._responses: t.Optional[gnmi.SubscribeResponse] = None

    def run(self) -> None:
        self._responses = self.client.subscribe(self.requests())
        try:
            for response in self._responses:
                self._response_queue.put(response)
        except grpc.RpcError as err:
            if isinstance(err, grpc.Call) and err.code() == grpc.StatusCode.CANCELLED:
                # cancelled locally
                pass
            elif isinstance(err, grpc.Call) and 'EOF' in err.details():
                # some devices throw this when the request stream is closed
                pass
            else:
                raise
        finally:
            self._response_queue.put(None)

    def requests(self) -> t.Iterator[gnmi.SubscribeRequest]:
        while (slitem := self._slist_queue.get()) is not None:
            if isinstance(slitem, gnmi.SubscriptionList):
                yield gnmi.SubscribeRequest(subscribe=slitem)
            elif isinstance(slitem, gnmi.Poll):
                yield gnmi.SubscribeRequest(poll=slitem)
        if self._responses is not None:
            self._responses.cancel()

    def enqueue(self, item: SlistType) -> None:
        self._slist_queue.put(item)

    def raw_responses(self, timeout: int) -> t.Iterator[gnmi.SubscribeResponse]:
        if not self.is_alive():
            # yield only queued updates
            for _ in range(self._response_queue.qsize()):
                if (response := self._response_queue.get()) is None:
                    return
                yield response
        else:
            while (response := self._response_queue.get(timeout=timeout)) is not None:
                yield response
            self.join()

    def responses(self, timeout: int, msg: t.Optional[str] = None) \
            -> t.Iterator[gnmi.SubscribeResponse]:
        if msg is None:
            msg = NO_SYNC_RESPONSE
        try:
            yield from self.raw_responses(timeout)
        except queue.Empty as e:
            raise AssertionError(msg) from e


class SubscribeLibrary(CapabilitiesLibrary):
    "ROBOT test suite library for servicing the gNMI SubscribeRequest tests."
    ROBOT_LIBRARY_SCOPE = 'SUITE'

    def __init__(self, lib_config: t.Dict[str, t.Any]) -> None:
        super().__init__(lib_config)
        self.paths: t.Tuple[str, ...] = ()
        self.requester: t.Optional[Requester] = None

    def close_client(self) -> None:
        self.paths = ()
        self.close_subscription()
        super().close_client()

    def close_subscription(self) -> None:
        if self.requester is not None:
            self.requester.enqueue(None)
            self.requester.join(2)
        self.requester = None

    def subscribe(self, mode: str, encoding: str, stream_mode: t.Optional[str] = None) -> None:
        paths = [make_gnmi_path(path) for path in self.paths]
        iencoding = encoding_str_to_int(encoding)
        prefix = make_gnmi_path('')
        if mode == 'STREAM' and stream_mode is not None:
            slist = ConfDgNMIClient.make_subscription_list(prefix, paths, mode,
                                                           iencoding, stream_mode)
        else:
            slist = ConfDgNMIClient.make_subscription_list(prefix, paths, mode, iencoding)
        self.requester = Requester(self._client)
        self.requester.start()
        self.requester.enqueue(slist)

    def check_updates(self, timeout: int) -> None:
        # Check if there is a nonempty notification update
        try:
            next(update
                 for response in self.requester.raw_responses(timeout)
                 for update in response.update.update)
        except StopIteration as e:
            raise AssertionError('The server did not send any updates') from e

    def subscription_paths(self, *paths: str) -> None:
        self.paths = paths

    def check_responses_terminated(self, timeout: int) -> None:
        for rsp in self._iterate_initial_responses(timeout):
            pass

    def _iterate_initial_responses(self, timeout: int) -> t.Iterator[gnmi.SubscribeResponse]:
        yield from self._iterate_synced_responses(timeout, True)

    def _iterate_synced_responses(self, timeout: int, abort_on_timeout: bool) \
            -> t.Iterator[gnmi.SubscribeResponse]:
        response_iterator = self.requester.responses(timeout) if abort_on_timeout \
            else self.requester.raw_responses(timeout)
        for response in response_iterator:
            if response.sync_response:
                return
            yield response

    def check_stream_closed(self, timeout: int) -> None:
        NOT_CLOSED = 'The server did not close the stream'
        try:
            next(self.requester.raw_responses(timeout))
            # there still was something in the stream
            raise AssertionError(NOT_CLOSED)
        except StopIteration:
            # this is ok
            return
        except queue.Empty as e:
            # caused by timeout - the stream has not been closed
            raise AssertionError(NOT_CLOSED) from e

    def get_initial_subscribe_config(self, timeout: int) -> GNMIConfigTree:
        config = GNMIConfigTree()
        for response in self._iterate_initial_responses(timeout):
            apply_response(config, response, UpdateType.STRUCTURE)
        return config

    def check_on_change_updates(self, timeout: int, update_time: int) -> None:
        config = self.get_initial_subscribe_config(timeout)
        self._wait_on_change_updates(config, timeout, update_time)

    def _wait_on_change_updates(self, config: GNMIConfigTree, timeout: int, update_time) -> None:
        responses = False
        NO_UPDATES = 'No updates were received'
        now = dt.now()
        try:
            for response in self.requester.raw_responses(timeout):
                responses = apply_response(config, response, UpdateType.VALUE)
                if (dt.now() - now).seconds >= update_time:
                    break
        except queue.Empty:
            if (dt.now() - now).seconds < update_time:
                raise AssertionError(NO_UPDATES)
        assert responses, NO_UPDATES

    def check_sample_updates(self, period: int, count: int, timeout: int) -> None:
        initial_tree = self.get_initial_subscribe_config(timeout)
        for index in range(count):
            sample_tree = GNMIConfigTree()
            sample_msg = f'Sample {index+1} not received within {period} seconds'
            cover_msg = f'Sample {index+1} does not cover the full tree'
            response = next(self.requester.responses(period, sample_msg))
            apply_response(sample_tree, response, UpdateType.STRUCTURE)
            next_responses = self.requester.responses(timeout, cover_msg)
            while not initial_tree.covered(sample_tree):
                response = next(next_responses)
                apply_response(sample_tree, response, UpdateType.STRUCTURE)
