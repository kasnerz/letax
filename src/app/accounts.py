#!/usr/bin/env python3

import yaml
import pandas as pd
import os
import streamlit_authenticator as stauth
import utils


class AccountManager:
    def __init__(self):
        self.accounts_file = os.path.join(
            os.path.dirname(os.path.realpath(__file__)), "accounts.yaml"
        )
        self.accounts = None

    def save_accounts(self, authenticator, accounts):
        if authenticator:
            authenticator.authentication_handler.credentials = accounts["credentials"]
            authenticator.authentication_handler.pre_authorized = {
                "emails": accounts["preauthorized_emails"]
            }

        self.accounts = accounts

        with open(self.accounts_file, "w") as f:
            yaml.dump(accounts, f)

    def get_accounts(self, authenticator):
        if not self.accounts:
            utils.log("Reloading accounts...")

            with open(self.accounts_file) as f:
                self.accounts = yaml.load(f, Loader=yaml.FullLoader)

        if authenticator:
            # update accounts
            self.accounts[
                "credentials"
            ] = authenticator.authentication_handler.credentials

        if self.accounts["credentials"]["usernames"] is None:
            # None would be non-iterable, we need an empty dict
            self.accounts["credentials"]["usernames"] = {}

        return self.accounts

    def get_user_by_username(self, authenticator, username):
        accounts = self.get_accounts(authenticator)

        user = accounts["credentials"]["usernames"].get(username)
        if user:
            user["username"] = username

        return user

    def update_user_name(self, authenticator, username, name):
        accounts = self.get_accounts(authenticator)

        accounts["credentials"]["usernames"][username]["name"] = name.strip()

        self.save_accounts(authenticator, accounts)

    def get_user_by_email(self, authenticator, email):
        accounts = self.get_accounts(authenticator)

        for username, user in accounts["credentials"]["usernames"].items():
            if user["email"].lower() == email.lower():
                user["username"] = username
                return user

    def update_or_create_account(
        self,
        authenticator,
        orig_username,
        username,
        name,
        email,
        role,
    ):
        accounts = self.get_accounts(authenticator)
        if orig_username == username:
            # update
            accounts["credentials"]["usernames"][username]["name"] = name.strip()
            accounts["credentials"]["usernames"][username]["email"] = email
            accounts["credentials"]["usernames"][username]["role"] = role
        else:
            accounts["credentials"]["usernames"][username] = accounts["credentials"][
                "usernames"
            ].pop(orig_username)
            accounts["credentials"]["usernames"][username]["username"] = username

        self.save_accounts(authenticator, accounts)

    def delete_account(self, authenticator, username):
        accounts = self.get_accounts(authenticator)

        del accounts["credentials"]["usernames"][username]

        self.save_accounts(authenticator, accounts)

    def set_password(self, authenticator, username, new_password):
        accounts = self.get_accounts(authenticator)
        user = accounts["credentials"]["usernames"].get(username)
        if not user:
            raise ValueError(f"User {username} not found")

        password_hash = stauth.utilities.hasher.Hasher([new_password]).generate()[0]

        accounts["credentials"]["usernames"][username]["password"] = password_hash

        self.save_accounts(authenticator, accounts)
        return True

    def get_preauthorized_accounts(self, authenticator):
        accounts = self.get_accounts(authenticator)
        # emails which are not registered for X-Challenge but are allowed to register in the app (admins etc.)
        return accounts["preauthorized_emails"]

    def get_preauthorized_account(self, authenticator, email):
        email = email.lower()
        accounts = self.get_accounts(authenticator)

        return accounts["preauthorized_emails"].get(email)

    def add_preauthorized_account(self, authenticator, email, role):
        accounts = self.get_accounts(authenticator)

        accounts["preauthorized_emails"][email] = {"role": role}

        self.save_accounts(authenticator, accounts)
