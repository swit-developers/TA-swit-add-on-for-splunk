import os
import sys
import json
import traceback
import time
from typing import Optional

import requests
import pytz

from datetime import datetime

sys.path.append(os.path.dirname(__file__))
from splunklib import client
from splunklib.modularinput import Script, Scheme, Argument, Event, EventWriter
from splunklib.binding import HTTPError
from utils import SwitTokens, log


class AuditLog(Script):
    _swit_tokens: Optional[SwitTokens]
    _event_writer: Optional[EventWriter]
    _named_service: Optional[client.Service]

    def __init__(self):
        super().__init__()
        self._swit_tokens = None
        self._event_writer = None
        self._named_service = None

    def get_scheme(self):
        scheme = Scheme("Swit Audit Logs Modular Input")
        scheme.title = "Swit Audit Logs"
        scheme.description = "Collect audit logs from Swit"
        scheme.use_external_validation = True
        scheme.use_single_instance = False

        start_time_argument = Argument("start_time")
        start_time_argument.title = "Start time"
        start_time_argument.data_type = Argument.data_type_string
        start_time_argument.description = "The start time to fetch audit logs from in the format YYYY-MM-DD HH:MM:SS (UTC)"
        start_time_argument.required_on_create = True
        scheme.add_argument(start_time_argument)

        des_argument = Argument("description")
        des_argument.title = "Description"
        des_argument.data_type = Argument.data_type_number
        des_argument.description = "A description for this input"
        des_argument.required_on_create = False
        scheme.add_argument(des_argument)

        return scheme

    def validate_input(self, validation_definition):
        # Validate the start time
        try:
            start_time_input = validation_definition.parameters.get('start_time')
            start_time = convert_user_input_time_to_epoch(start_time_input)
        except ValueError:
            raise ValueError(
                "The start time should be in the format of YYYY-MM-DD HH:MM:SS")
        current_time = int(time.time() * 1000)
        if current_time - start_time > 1000 * 60 * 60 * 24 * 365:
            raise ValueError(
                "The start time should not be more than a year ago")

        # Validate the interval
        interval_input = validation_definition.parameters.get('interval')
        interval = float(interval_input)
        if interval < 30:
            raise ValueError(
                "The interval cannot shorter than 30 seconds.")

    def stream_events(self, inputs, ew):
        try:
            self._event_writer = ew
            # We can't use the given self.service for tokens
            # because it does not allow updating the tokens without the owner specified.
            self._swit_tokens = SwitTokens(client.connect(
                    scheme=self.service.scheme,
                    host=self.service.host,
                    port=self.service.port,
                    token=self.service.token,
                    owner='nobody',
                ))
            for input_name, input_item in list(inputs.inputs.items()):
                # Unfortunately, access to the collection needs the app name specified.
                self._named_service = client.connect(
                    scheme=self.service.scheme,
                    host=self.service.host,
                    port=self.service.port,
                    token=self.service.token,
                    owner='nobody',
                    app=input_item.get('__app')
                )
                self._update_audit_logs(input_name, input_item)
        except Exception as e:
            error_message = traceback.format_exc()
            log(error_message)

    def _update_audit_logs(self, input_name, input_item):
        input_start_time = convert_user_input_time_to_epoch(input_item["start_time"])
        current_time = int(time.time() * 1000) - 10000  # 10 seconds ago to avoid missing logs

        if input_start_time > current_time:
            return

        try:
            checkpoint = self._collection_data.query_by_id(input_name)
        except HTTPError:
            checkpoint = {
                "_key": input_name
            }

        # When the input is first created, fetch all past logs from the specified start time
        first_event_time = checkpoint.get("first_event_time") or current_time  # 13-digit epoch
        initial_first_event_time = first_event_time
        next_page_token = None
        while first_event_time > input_start_time:
            data = self._get_audit_logs(input_start_time, initial_first_event_time, next_page_token)
            next_page_token = data["next_page_token"]
            items = data["items"]
            self._write_events(input_name, items)
            if next_page_token and items:
                first_event_time = convert_to_epoch(items[-1]["event_time"])
            else:
                first_event_time = input_start_time
            checkpoint.update({
                "first_event_time": first_event_time
            })
            try:
                self._collection_data.update(input_name, checkpoint)
            except HTTPError:
                self._collection_data.insert(checkpoint)

        # Fetch logs from the last checkpoint to the current time
        last_event_time = checkpoint.get("last_event_time")  # 13-digit epoch
        next_page_token = None
        while last_event_time:
            data = self._get_audit_logs(last_event_time + 1, current_time, next_page_token)
            next_page_token = data["next_page_token"]
            items = data["items"]
            self._write_events(input_name, items)
            if not next_page_token or not items:
                break
        checkpoint.update({
            "last_event_time": current_time
        })
        try:
            self._collection_data.update(input_name, checkpoint)
        except HTTPError:
            self._collection_data.insert(checkpoint)

    def _get_audit_logs(self, start_time, end_time, next_page_token):
        url = "https://openapi.swit.io/v1/api/audit.log.list"
        response = requests.get(url, headers={
            "Authorization": f"Bearer {self._swit_tokens.access_token}"
        }, params={
            "page_size": 500,
            "page_token": next_page_token,
            "start_time": start_time,
            "end_time": end_time
        })
        if response.status_code == 401:
            self._swit_tokens.refresh()
            r = response.request
            r.prepare_headers({
                "Authorization": f"Bearer {self._swit_tokens.access_token}"
            })
            with requests.Session() as s:
                response = s.send(r)

        response.raise_for_status()
        return response.json()

    @property
    def _collection_data(self) -> client.KVStoreCollectionData:
        collection_name = "swit_audit_logs_checkpoints"
        assert self._named_service
        swit_collection = next(collection for collection
                               in self._named_service.kvstore
                               if collection.name == collection_name)
        return swit_collection.data

    def _write_events(self, input_name, log_items):
        for log_item in log_items:
            event_time = convert_to_epoch(log_item["event_time"])
            event = Event(
                stanza=input_name,
                time="%.3f" % (event_time / 1000),
                data=json.dumps(log_item),
                sourcetype="audit_log",
                unbroken=True,
                done=True
            )
            self._event_writer.write_event(event)


def convert_to_epoch(time_string):
    try:
        return int(datetime.strptime(time_string, '%Y-%m-%dT%H:%M:%S.%fZ').replace(
            tzinfo=pytz.UTC).timestamp() * 1000)
    except ValueError:
        return int(datetime.strptime(time_string, '%Y-%m-%dT%H:%M:%SZ').replace(
            tzinfo=pytz.UTC).timestamp() * 1000)

def convert_user_input_time_to_epoch(time_string):
    return int(datetime.strptime(
            time_string, '%Y-%m-%d %H:%M:%S').replace(
            tzinfo=pytz.UTC).timestamp() * 1000)


if __name__ == "__main__":
    sys.exit(AuditLog().run(sys.argv))
