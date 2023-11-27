#!/usr/bin/env python3

from database import get_database
from datetime import datetime
import copy
import streamlit as st
import streamlit_authenticator as stauth
import time
import time
import utils

db = get_database()


def get_logged_info():
    username = st.session_state["username"]
    user = db.am.get_user_by_username(username)

    if not user:
        st.stop()

    participant = db.get_participant_by_email(user["email"])
    user["pax_id"] = participant["id"] if participant else None

    if not user:
        st.stop()

    team = db.get_team_for_user(user["pax_id"])

    return user, team


def register_new_user(config):
    username, user = db.am.get_registered_user(config)

    if username is None:
        st.error("Tento email je již zaregistrován.")
        st.stop()

    # if the user is allowed to register through extra accounts, find their role
    extra_account = db.am.get_extra_account(user["email"].lower())
    role = extra_account["role"] if extra_account else "user"

    db.am.add_user(
        username=username,
        email=user["email"].lower(),
        name=user["name"],
        password_hash=user["password"],
        registered=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        role=role,
    )
    utils.clear_cache()


def reset_password_form(authenticator):
    st.info(
        "Zadej své uživatelské jméno, nové heslo ti přijde na e-mail. Ve svém účtu ho můžeš později změnit."
    )
    (
        username_forgot_pw,
        email_forgot_password,
        random_password,
    ) = authenticator.forgot_password("Zapomenuté heslo")

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
                    Tvoje nové heslo do systému pro letní X-Challenge je: <b>{random_password}</b>
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
                db.am.set_password(username_forgot_pw, random_password)
                st.success(
                    "Nové heslo odesláno na email. Pokud nepřišel do pár minut, zkontroluj spam."
                )
            else:
                st.error(
                    "Omlouváme se, e-mail se nepodařilo odeslat. Zkus to prosím znovu."
                )


def register_form(authenticator, config):
    try:
        if authenticator.register_user("Zaregistrovat se"):
            register_new_user(config)

            utils.clear_cache()
            st.success("Uživatel úspěšně zaregistrován. Nyní se můžeš přihlásit.")
            st.balloons()
            # time.sleep(5)
            # st.rerun()

    except Exception as e:
        st.error(e)


def create_authenticator():
    preauthorized = db.get_preauthorized_emails()
    config = copy.deepcopy(db.am.accounts)

    authenticator = stauth.Authenticate(
        config["credentials"],
        config["cookie"]["name"],
        config["cookie"]["key"],
        config["cookie"]["expiry_days"],
        preauthorized,
    )
    return authenticator, config


def login_page():
    authenticator, config = create_authenticator()
    tabs = None

    # delete query parameters
    st.experimental_set_query_params()

    if st.session_state["authentication_status"] == None:
        _, center_column, _ = st.columns([1, 3, 1])
        with center_column:
            tabs = st.tabs(["Přihlásit se", "Zaregistrovat se", "Reset hesla"])
            with tabs[0]:
                res = authenticator.login("Přihlásit se", "main")
            with tabs[1]:
                st.info(
                    """- **Email** použij stejný, jako jsi použil(a) pro registraci na akci (malými písmeny). 
- **Username** je libovolný identifikátor, které budeš používat na přihlášení do systému.
- **Name** je tvoje celé jméno a příjmení.
- **Heslo** použij takové, které se ti bude dobře pamatovat, dobře psát na mobilu, a zároveň ho nenajdeš [tady](https://en.wikipedia.org/wiki/Wikipedia:10,000_most_common_passwords) :)

Pokud tě na akci přihlásil někdo jiný nebo se ti z nějakého důvodu nedaří zaregistrovat, tak nám napiš svoje jméno, příjmení a e-mail (ideálně s dokladem o zaplacení) na letni@x-challenge.cz, přidáme tě do databáze ručně."""
                )
                register_form(authenticator, config)

            if res[0] is not None:
                # this is necessary to display the user interface right after login and not showing all the tabs
                st.session_state["name"] = res[0]
                st.session_state["authentication_status"] = res[1]
                st.session_state["username"] = res[2]
                time.sleep(0.1)

                st.rerun()

        with tabs[2]:
            reset_password_form(authenticator)

    if st.session_state["authentication_status"] == True:
        # if tabs:
        # del tabs

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

    elif st.session_state["authentication_status"] == False:
        st.error("Nesprávné přihlašovací údaje.")
        st.info("Před prvním přihlášením se musíš zaregistrovat.")
        st.session_state["authentication_status"] = None

        return None, None
