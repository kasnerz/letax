#!/usr/bin/env python3

from database import get_database
from datetime import datetime
import copy
import streamlit as st
import streamlit_authenticator as stauth
import time
import time
import utils
import extra_streamlit_components as stx

params = st.query_params
event_id = utils.get_event_id(params)
db = get_database(event_id=event_id)


def get_logged_info():
    username = st.session_state["username"]
    authenticator = st.session_state.get("authenticator")
    user = db.am.get_user_by_username(authenticator, username)
    if not user:
        st.stop()

    participant = db.get_participant_by_email(user["email"])
    user["pax_id"] = participant["id"] if participant else None

    if not user:
        st.stop()

    team = db.get_team_for_user(user["pax_id"])

    return user, team


def register_new_user(authenticator, email, username):
    # if the user is allowed to register through extra accounts, find their role
    extra_account = db.am.get_preauthorized_account(authenticator, email)
    role = extra_account["role"] if extra_account else "user"

    user = authenticator.authentication_handler.credentials["usernames"][username]
    user["role"] = role
    user["registered"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # authenticator is up-to-date, we just need to update the accounts
    accounts = db.am.get_accounts(authenticator)
    db.am.save_accounts(authenticator, accounts)


def reset_password_form(authenticator):
    st.info(
        "Zadej své uživatelské jméno, nové heslo ti přijde na e-mail. Ve svém účtu ho můžeš později změnit."
    )
    (
        username_forgot_pw,
        email_forgot_password,
        random_password,
    ) = authenticator.forgot_password(
        fields={
            "Form name": "Zapomenuté heslo",
            "Username": "Uživatelské jméno",
        },
        location="main",
    )

    if username_forgot_pw is None:
        st.stop()

    if username_forgot_pw is False:
        st.error("Uživatel nebyl nalezen.")

    else:
        with st.spinner("Odesílám e-mail, chvilku strpení..."):
            content_html = f"""
                <html>
                <body>
                    <p>Ahoj <b>{username_forgot_pw}</b>!<br>
                    <br>
                    Tvoje nové heslo do systému pro Letní X-Challenge je: <b>{random_password}</b>
                    <br>
                    <br>
                    Hodně zdaru!
                    <br>
                    Tým X-Challenge
                    </p>
                </body>
                </html>"""
            # send e-mail to user
            ret = utils.send_email(
                address=email_forgot_password,
                subject="X-Challenge: Reset hesla",
                content_html=content_html,
            )
            if ret:
                db.am.set_password(authenticator, username_forgot_pw, random_password)
                st.success(
                    "Nové heslo odesláno na email. Pokud nepřišel do pár minut, zkontroluj spam."
                )
            else:
                st.error(
                    "Omlouváme se, e-mail se nepodařilo odeslat. Zkus to prosím znovu."
                )


def register_form(authenticator):
    try:
        email, username, name = authenticator.register_user(
            fields={
                "Form name": "Zaregistrovat se",
                "Name": "Jméno a příjmení",
                "Username": "Uživatelské jméno (pro přihlašování, čti instrukce výše)",
                "Password": "Heslo",
                "Repeat password": "Heslo znovu",
            },
            pre_authorization=True,
        )
        if email:
            register_new_user(authenticator, email, username)

            st.success("Uživatel úspěšně zaregistrován. Nyní se můžeš přihlásit.")
            st.balloons()

    except Exception as e:
        st.error(e)


def create_authenticator():
    # this is necessary to prevent multiple page reloads
    if "authenticator" in st.session_state:
        auth = st.session_state["authenticator"]

        if not st.session_state["authentication_status"]:
            # this hack seems to be able to retrieve the cookie and correctly log the user after the page refresh
            auth.cookie_handler.cookie_manager = stx.CookieManager()
            token = auth.cookie_handler.get_cookie()
            if token:
                auth.authentication_handler.execute_login(token=token)

        return auth

    preauthorized = {"emails": db.get_preauthorized_emails()}
    config = db.am.get_accounts(authenticator=None)

    st.session_state["authenticator"] = stauth.Authenticate(
        credentials=config["credentials"],
        cookie_name=config["cookie"]["name"],
        cookie_key=config["cookie"]["key"],
        cookie_expiry_days=config["cookie"]["expiry_days"],
        pre_authorized=preauthorized,
    )
    return st.session_state["authenticator"]


def incorrect_login_details():
    st.error("Nesprávné přihlašovací údaje.")
    st.info("Před prvním přihlášením se musíš zaregistrovat.")
    st.session_state["authentication_status"] = None

    return None, None


def login_page():
    tabs = None

    # delete query parameters
    st.query_params.clear()

    authenticator = create_authenticator()
    status = st.session_state.get("authentication_status")

    if status is True:
        username_container = st.sidebar.container()
        authenticator.logout("Odhlásit se", "sidebar")

        user, team = get_logged_info()
        if not user:
            st.error("Uživatel není přihlášen.")
            st.stop()

        username_container.markdown("### Uživatel")
        username_container.markdown(
            f'{"🧑‍🔧 " if user["role"] == "admin" else "🧒 "}**{user["name"]}** ({user["username"]})'
        )

        return user, team

    elif status is False:
        incorrect_login_details()

    elif status is None:
        _, center_column, _ = st.columns([1, 3, 1])

        with center_column:
            tabs = st.tabs(["Přihlásit se", "Zaregistrovat se", "Reset hesla"])
            with tabs[0]:
                res = authenticator.login(
                    fields={
                        "Form name": "Přihlásit se",
                        "Username": "Uživatelské jméno",
                        "Password": "Heslo",
                    },
                    location="main",
                )

                # if status is not True and st.session_state["authentication_status"] is True:
                if res[0] is not None:
                    # this is necessary to display the user interface right after login and not showing all the tabs
                    st.session_state["name"] = res[0]
                    st.session_state["authentication_status"] = res[1]
                    st.session_state["username"] = res[2]
                    time.sleep(0.5)

                    st.rerun()

                if res[1] is False:
                    incorrect_login_details()

            with tabs[1]:
                st.info(
                    """- **Email** použij stejný, jako jsi použil(a) pro registraci na akci.
- **Uživatelské jméno** je identifikátor, které budeš používat na přihlášení do systému. Může obsahovat **pouze** písmena anglické abecedy, čísla, podtržítko (_), pomlčku (-) a tečku (.).
- **Heslo** použij takové, které se ti bude dobře pamatovat, dobře psát na mobilu, a zároveň ho nenajdeš [tady](https://en.wikipedia.org/wiki/Wikipedia:10,000_most_common_passwords).

Pokud tě na akci přihlásil někdo jiný nebo se ti ani po přečtení všech instrukcí z nějakého důvodu nedaří zaregistrovat, tak nám napiš svoje jméno, příjmení a e-mail (ideálně s dokladem o zaplacení) na letni@x-challenge.cz, přidáme tě do databáze ručně.

Pokud dostaneš hlášku \"Email already taken\", už máš pravděpodobně založený účet z předchozích ročníků - přihlas se, případně si vyresetuj heslo."""
                )
                register_form(authenticator)

        with tabs[2]:
            reset_password_form(authenticator)
