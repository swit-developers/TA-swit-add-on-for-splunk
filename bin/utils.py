import os
import sys
import requests

sys.path.append(os.path.dirname(__file__))
from splunklib.client import Service, StoragePasswords
from dotenv import load_dotenv

load_dotenv()


class SwitTokens:
    _storage_passwords: StoragePasswords

    def __init__(self, service: Service):
        self._storage_passwords = service.storage_passwords
        self._ACCESS_TOKEN_KEY = "swit_access_token"
        self._REFRESH_TOKEN_KEY = "swit_refresh_token"
        self._USERNAME = "-"

    @property
    def access_token(self):
        return next((p.clear_password for p in self._storage_passwords
                     if p.realm == self._ACCESS_TOKEN_KEY and p.username == self._USERNAME), None)

    @property
    def refresh_token(self):
        return next((p.clear_password for p in self._storage_passwords
                     if p.realm == self._REFRESH_TOKEN_KEY and p.username == self._USERNAME), None)

    def refresh(self, new_refresh_token=None):
        log("refreshing the token...")
        refresh_url = "https://splunk.switstore.io/refresh"
        response = requests.post(
            refresh_url,
            json={
                'refresh_token': new_refresh_token or self.refresh_token
            },
            headers={
                'Content-Type': 'application/json'
            }
        )
        response.raise_for_status()

        # Update the access token
        new_access_token = response.json()["access_token"]
        if self.access_token != new_access_token:
            if self.access_token:
                self._storage_passwords.delete(self._USERNAME, self._ACCESS_TOKEN_KEY)
            self._storage_passwords.create(new_access_token, self._USERNAME, self._ACCESS_TOKEN_KEY)

        # Update the refresh token
        new_refresh_token = response.json()["refresh_token"]
        if self.refresh_token != new_refresh_token:
            if self.refresh_token:
                self._storage_passwords.delete(self._USERNAME, self._REFRESH_TOKEN_KEY)
            self._storage_passwords.create(new_refresh_token, self._USERNAME, self._REFRESH_TOKEN_KEY)


def log(*data):
    print(data)
    logger_endpoint = os.environ.get("LOGGER_ENDPOINT")
    if logger_endpoint:
        requests.post(logger_endpoint, json={
            'content': [repr(d) for d in data]
        })
