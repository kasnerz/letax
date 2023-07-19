#!/usr/bin/env python3

import yaml
import pandas as pd
import os
import streamlit_authenticator as stauth


class AccountManager:
    def __init__(self):
        self.accounts_file = os.path.join(os.path.dirname(os.path.realpath(__file__)), "accounts.yaml")
        self.load_accounts()

        self.email_index = {}
        self.recompute_index()

    def load_accounts(self):
        print("Reloading accounts...")
        with open(self.accounts_file) as f:
            self.accounts = yaml.load(f, Loader=yaml.FullLoader)

        if not self.accounts["credentials"]["usernames"]:
            # None would be non-iterable, we need an empty dict
            self.accounts["credentials"]["usernames"] = {}

    def save_accounts(self):
        with open(self.accounts_file, "w") as f:
            yaml.dump(self.accounts, f)

        self.recompute_index()

    def recompute_index(self):
        # users indexed by email, `username` added as value
        self.email_index = {
            user["email"]: {"username": username, **user}
            for username, user in self.accounts["credentials"]["usernames"].items()
        }

    def get_user_by_username(self, username):
        user = self.accounts["credentials"]["usernames"].get(username)
        if user:
            user["username"] = username

        return user

    def get_user_by_email(self, email):
        return self.email_index.get(email)

    def add_user(self, username, email, name, password_hash, registered, role):
        self.accounts["credentials"]["usernames"][username] = {
            "email": email,
            "name": name,
            "password": password_hash,
            "registered": registered,
            "role": role,
        }

        self.save_accounts()

    def get_registered_user(self, config):
        # there is no way to tell which user just registered except for comparing the old and new config files
        old_emails = {user["email"] for user in self.accounts["credentials"]["usernames"].values()}
        new_emails = {user["email"] for user in config["credentials"]["usernames"].values()}

        if len(new_emails) == len(old_emails):
            # no new user
            return None, None

        new_email = list(new_emails - old_emails)[0]
        username, user = [user for user in config["credentials"]["usernames"].items() if user[1]["email"] == new_email][
            0
        ]

        return username, user

    def get_extra_accounts(self):
        # emails which are not registered for X-Challenge but are allowed to register in the app (admins etc.)
        return self.accounts["preauthorized_emails"]

    def get_extra_account(self, email):
        return self.accounts["preauthorized_emails"].get(email)

    def get_accounts_as_df(self):
        users = self.accounts["credentials"]["usernames"]
        users = [{"username": username, **user} for username, user in users.items()]

        df = pd.DataFrame(users)
        df = df.drop(columns=["password"])
        return df

    def save_accounts_from_df(self, df):
        for _, row in df.iterrows():
            row_dict = row.to_dict()
            username = row_dict["username"]
            del row_dict["username"]

            if row_dict.get("pax_id"):
                del row_dict["pax_id"]

            for key, value in row_dict.items():
                self.accounts["credentials"]["usernames"][username][key] = value

        self.save_accounts()

    def get_preauthorized_emails_as_df(self):
        preauth = self.accounts["preauthorized_emails"]
        preauth = [{"email": email, **user} for email, user in preauth.items()]

        df = pd.DataFrame(preauth)
        return df

    def save_preauthorized_emails_from_df(self, df):
        for _, row in df.iterrows():
            row_dict = row.to_dict()
            email = row_dict["email"]

            if email is None:
                continue

            del row_dict["email"]

            self.accounts["preauthorized_emails"][email] = row_dict

        print(self.accounts["preauthorized_emails"])

        self.save_accounts()

    def set_password(self, username, new_password):
        user = self.accounts["credentials"]["usernames"].get(username)
        if not user:
            raise ValueError(f"User {username} not found")

        password_hash = stauth.Hasher([new_password]).generate()[0]

        self.accounts["credentials"]["usernames"][username]["password"] = password_hash

        self.save_accounts()
        return True
