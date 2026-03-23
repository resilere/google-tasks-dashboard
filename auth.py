from google_auth_oauthlib.flow import InstalledAppFlow
from google.oauth2.credentials import Credentials
import os
import pickle

SCOPES = ["https://www.googleapis.com/auth/tasks"]

def get_credentials():

    if os.path.exists("token.pkl"):
        with open("token.pkl", "rb") as f:
            creds = pickle.load(f)
        return creds

    flow = InstalledAppFlow.from_client_secrets_file(
        "client_secret.json",
        SCOPES
    )

    creds = flow.run_local_server(port=0)

    with open("token.pkl", "wb") as f:
        pickle.dump(creds, f)

    return creds