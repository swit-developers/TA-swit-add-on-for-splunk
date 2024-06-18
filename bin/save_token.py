import json
import os
import sys
import traceback

from urllib.parse import urlparse

from requests import HTTPError
from splunk.persistconn.application import PersistentServerConnectionApplication

sys.path.append(os.path.dirname(__file__))
from splunklib import client
from utils import SwitTokens, log


class SaveToken(PersistentServerConnectionApplication):
    def __init__(self, _command_line, _command_arg):
        super(PersistentServerConnectionApplication, self).__init__()

    def handle(self, in_string):
        try:
            handle_request(in_string)
            return {
                'payload': {
                    'message': 'Tokens saved successfully'
                },
                'status': 200
            }
        except HTTPError as e:
            return {
                'payload': {
                    'message': e.response.json().get('message')
                },
                'status': e.response.status_code
            }
        except Exception as e:
            error_message = traceback.format_exc()
            log(error_message)
            return {
                'payload': {
                    'message': repr(e)
                },
                'status': 500
            }


def handle_request(in_string):
    data = json.loads(in_string)
    authtoken = data['session']['authtoken']
    rest_uri = data['server']['rest_uri']
    parsed_url = urlparse(rest_uri)

    # Connect to the Splunk instance
    service = client.connect(
        scheme=parsed_url.scheme,
        host=parsed_url.hostname,
        port=parsed_url.port,
        token=authtoken,
        owner='nobody',
    )
    payload = json.loads(data['payload'])
    refresh_token = payload.get('refresh_token')
    swit_tokens = SwitTokens(service)
    swit_tokens.refresh(refresh_token)
