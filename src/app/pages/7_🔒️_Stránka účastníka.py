from database import get_database
from datetime import datetime
from streamlit_js_eval import get_geolocation
import accounts
import copy
import os
import pandas as pd
import streamlit as st
import streamlit_authenticator as stauth
import time
import time
import traceback
import utils

st.set_page_config(page_title="Stránka týmu", page_icon="static/favicon.png", layout="wide")
utils.style_sidebar()

db = get_database()


def register_new_user(config):
    username, user = db.am.get_registered_user(config)

    if username is None:
        st.error("Tento email je již zaregistrován.")
        st.stop()

    # if the user is allowed to register through extra accounts, find their role
    extra_account = db.am.get_extra_account(user["email"])
    role = extra_account["role"] if extra_account else "user"

    db.am.add_user(
        username=username,
        email=user["email"],
        name=user["name"],
        password_hash=user["password"],
        registered=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        role=role,
    )


def reset_password_form(authenticator):
    st.info(
        "Ale to snad ne! Nevíš svoje heslo? Můžeme ti na mail poslat nové, ale pozor – bude se špatně pamatovat. Máš proto od nás novou výzvu 'Neville Longbottom'."
    )
    username_forgot_pw, email_forgot_password, random_password = authenticator.forgot_password("Zapomenuté heslo")

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
                st.success("Nové heslo odesláno na email. Pokud nepřišel do pár minut, zkontroluj spam.")
            else:
                st.error("Omlouváme se, e-mail se nepodařilo odeslat. Zkus to prosím znovu.")


def register_form(authenticator, config):
    try:
        if authenticator.register_user("Zaregistrovat se"):
            register_new_user(config)

            st.success("Uživatel úspěšně zaregistrován. Nyní se můžeš přihlásit.")
            st.balloons()
            # time.sleep(5)
            # st.experimental_rerun()

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


def create_post(user, action_type, action, comment, files):
    try:
        db.save_post(
            user=user,
            action_type=action_type,
            action=action,
            comment=comment,
            files=files,
        )
        st.success("Příspěvek odeslán.")
        st.balloons()
    except Exception as e:
        st.error(f"Stala se chyba: {traceback.print_exc()}")
        # print stacktrace
        traceback.print_exc()


def record_challenge(user):
    challenges = db.get_available_actions(user=user, action_type="challenge")

    with st.form("challenge"):
        challenge_idx = st.selectbox(
            "Výzva:",
            options=range(len(challenges)),
            format_func=lambda x: challenges[x]["name"],
        )
        # Create two text input fields
        comment = st.text_area(
            "Komentář:",
        )
        files = st.file_uploader("Foto / video:", accept_multiple_files=True)

        # Create a submit button
        submit_button = st.form_submit_button(label="Odeslat")

    # When the submit button is clicked
    if submit_button:
        with st.spinner("Ukládám příspěvek..."):
            create_post(
                user=user,
                action_type="challenge",
                action=challenges[challenge_idx],
                comment=comment,
                files=files,
            )


def record_checkpoint(user):
    checkpoints = db.get_available_actions(user=user, action_type="checkpoint")

    with st.form("checkpoint"):
        checkpoint_idx = st.selectbox(
            "Checkpoint:",
            options=range(len(checkpoints)),
            format_func=lambda x: checkpoints[x]["name"],
        )
        # Create two text input fields
        comment = st.text_area(
            "Komentář:",
        )
        files = st.file_uploader("Foto / video:", accept_multiple_files=True)

        # Create a submit button
        submit_button = st.form_submit_button(label="Odeslat")

    # When the submit button is clicked
    if submit_button:
        with st.spinner("Ukládám příspěvek..."):
            create_post(
                user=user,
                action_type="checkpoint",
                action=checkpoints[checkpoint_idx],
                comment=comment,
                files=files,
            )


def record_story(user):
    with st.form("story"):
        story_title = st.text_input(
            "Nadpis:",
        )
        # Create two text input fields
        comment = st.text_area(
            "Text:",
        )
        files = st.file_uploader("Foto / video:", accept_multiple_files=True)

        # Create a submit button
        submit_button = st.form_submit_button(label="Odeslat")

    # When the submit button is clicked
    if submit_button:
        with st.spinner("Ukládám příspěvek..."):
            create_post(
                user=user,
                action_type="story",
                action=story_title,
                comment=comment,
                files=files,
            )


def record_location(user, team):
    # cols = st.columns(3)

    # with cols[0]:
    st.markdown("#### Sdílení polohy")

    with st.form("location"):
        comment = st.text_input(
            "Komentář:",
        )
        btn_share = st.form_submit_button("📌 Zaznamenat polohu")

    is_visible = db.is_team_visible(team)
    st.checkbox(label="Veřejné sdílení polohy", value=is_visible, on_change=db.toggle_team_visibility, args=(team,))
    container = st.empty()

    last_location = db.get_last_location(team)
    if last_location is not None:
        st.markdown(f"#### Poslední poloha")
        st.write(f"{last_location['latitude']}, {last_location['longitude']}")
        st.caption(f"{last_location['date']}")
        st.map(pd.DataFrame([last_location]))

    if btn_share:
        location = get_geolocation()

        time.sleep(3)
        if location:
            coords = location["coords"]
            longitude = coords["longitude"]
            latitude = coords["latitude"]
            accuracy = coords["accuracy"]
            altitude = coords["altitude"]
            altitude_accuracy = coords["altitudeAccuracy"]
            heading = coords["heading"]
            speed = coords["speed"]
            date = datetime.fromtimestamp(location["timestamp"] / 1000.0)

            db.save_location(user, comment, longitude, latitude, accuracy, altitude, altitude_accuracy, heading, speed, date)
            container.success("Poloha nasdílena!")
        else:
            st.warning(
                "Nepodařilo se nasdílet polohu. Zkontroluj, jestli má tvůj prohlížeč přístup k tvé aktuální poloze."
            )
            time.sleep(5)


def show_team_info(user, team):
    username = user["username"]
    team_name = team["team_name"] if team else ""

    # all users not part of any team and not the current user
    available_paxes = db.get_available_participants(username, team)


    with st.form("team_info"):
        # team name
        team_name = st.text_input("Název týmu:", value=team_name)

        second_member = st.selectbox(
            "Další člen:",
            options=range(len(available_paxes)),
            format_func=lambda x: available_paxes.iloc[x]["name"],
        )
        team_motto = st.text_input("Motto týmu (nepovinné):")
        team_web = st.text_input("Instagram, web, apod. (nepovinné):")

        cols = st.columns([4, 1])
        with cols[0]:
            team_photo = st.file_uploader("Týmové foto (nepovinné):")
        with cols[1]:
            if team and team["team_photo"]:
                st.image(utils.resize_image(db.read_image(team["team_photo"]), crop_ratio="1:1"))
        submit_button = st.form_submit_button(label="Uložit tým")

    # When the submit button is clicked
    if submit_button:
        if not team_name:
            st.error("Musíš zadat jméno týmu")
            st.stop()

        second_member = available_paxes.iloc[second_member]["id"]

        db.add_or_update_team(
            team_name=team_name,
            team_motto=team_motto,
            team_web=team_web,
            team_photo=team_photo,
            first_member=user["pax_id"],
            second_member=second_member,
            current_team=team,
        )
        st.cache_resource.clear()
        st.success(f"Tým **{team_name}** uložen.")
        st.balloons()
        time.sleep(3)
        st.experimental_rerun()


def show_user_info(user):
    with st.form("user_info"):
        participant = db.get_participant_by_email(user["email"])
        emergency_contact_val = participant["emergency_contact"] or ""
        bio_val = participant["bio"] or ""
        bio = st.text_area("Pár slov o mně:", value=bio_val)
        emergency_contact = st.text_input("Nouzový kontakt (kdo + tel. číslo; neveřejné):", value=emergency_contact_val)

        cols = st.columns([4, 1])
        with cols[0]:
            photo = st.file_uploader("Profilové foto:")
        with cols[1]:
            photo_img = participant["photo"]

            if photo_img:
                st.image(utils.resize_image(db.read_image(photo_img), crop_ratio="1:1"))

        submit_button = st.form_submit_button(label="Uložit profilové informace")

    # When the submit button is clicked
    if submit_button:
        db.update_participant(
            username=user["username"], email=user["email"], bio=bio, emergency_contact=emergency_contact, photo=photo
        )
        st.cache_resource.clear()
        st.success(f"Informace uloženy.")
        st.balloons()
        time.sleep(3)
        st.experimental_rerun()


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


def show_settings_editor():
    if st.session_state.get(f"settings_data") is None:
        st.session_state[f"settings_data"] = db.get_settings_as_df()

    edited_df = st.data_editor(
        st.session_state[f"settings_data"],
        hide_index=True,
        use_container_width=True,
        # num_rows="dynamic",
        key=f"settings_data_editor",
        column_config={"key": st.column_config.Column(disabled=True)},
    )
    db.save_settings_from_df(edited_df)


def show_users_editor():
    if st.session_state.get(f"users_data") is None:
        st.session_state[f"users_data"] = db.am.get_accounts_as_df()

    edited_df = st.data_editor(
        st.session_state[f"users_data"],
        hide_index=True,
        use_container_width=True,
        # num_rows="dynamic",
        key=f"users_data_editor",
        column_config={
            "role": st.column_config.SelectboxColumn(options=["user", "admin"]),
            # "password": st.column_config.Column(disabled=True),
        },
    )
    edits = st.session_state[f"users_data_editor"]

    if any(list(edits.values())):
        db.am.save_accounts_from_df(edited_df)


def show_preauthorized_editor():
    if st.session_state.get(f"preauthorized_data") is None:
        st.session_state[f"preauthorized_data"] = db.am.get_preauthorized_emails_as_df()

    edited_df = st.data_editor(
        st.session_state[f"preauthorized_data"],
        hide_index=True,
        use_container_width=True,
        # num_rows="dynamic",
        key=f"preauthorized_data_editor",
        column_config={
            "role": st.column_config.SelectboxColumn(options=["user", "admin"]),
        },
    )
    edits = st.session_state[f"preauthorized_data_editor"]

    if any(list(edits.values())):
        db.am.save_preauthorized_emails_from_df(edited_df)


def show_db_data_editor(table, column_config=None):
    if st.session_state.get(f"{table}_data") is None or st.session_state.get(f"{table}_data_editor") is None:
        st.session_state[f"{table}_data"] = db.get_table_as_df(table_name=f"{table}")

    edited_df = st.data_editor(
        st.session_state[f"{table}_data"],
        hide_index=True,
        use_container_width=True,
        num_rows="dynamic",
        key=f"{table}_data_editor",
        column_config=column_config,
    )
    edits = st.session_state[f"{table}_data_editor"]

    if any(list(edits.values())):
        if edits["added_rows"] and edited_df.empty:
            # bug?
            edited_df = pd.DataFrame(edits["added_rows"], columns=edited_df.columns)

        db.save_df_as_table(edited_df, f"{table}")


def show_actions():
    st.markdown("#### Aktualizovat účastníky")

    st.caption("Načte seznam účastníků z WooCommerce")

    with st.form("fetch_wc_users"):
        product_id = st.text_input(
            "product_id", help="Číslo produktu Letní X-Challenge na webu", value=db.get_settings_value("product_id")
        )

        submit_button = st.form_submit_button(label="Aktualizovat účastníky")

    if submit_button:
        with st.spinner("Aktualizuji účastníky"):
            container = st.container()
            db.wc_fetch_participants(product_id=int(product_id), log_area=container)

        st.balloons()

    st.markdown("#### Cache")
    cache_btn = st.button("Vymazat cache", on_click=st.cache_resource.clear)

    if cache_btn:
        st.balloons()


def show_admin_page():
    st.title("Administrace")

    tab_notifications, tab_users, tab_paxes, tab_teams, tab_challenges, tab_checkpoints, tab_posts, tab_settings, tab_actions = st.tabs(
        ["🍍 Oznámení", "👤 Uživatelé", "🧒 Účastníci", "🧑‍🤝‍🧑 Týmy", "🏆 Výzvy", "📍 Checkpointy", "📝 Příspěvky", "⚙️ Nastavení", "🪛 Akce"]
    )

    with tab_notifications:
        show_db_data_editor(
            table="notifications",
            column_config={
                "type": st.column_config.SelectboxColumn(options=["info", "varování", "důležité", "skryté"]),
            },
        )

    with tab_paxes:
        show_db_data_editor(
            table="participants",
            column_config={
                "id": st.column_config.Column(width="small"),
                "email": st.column_config.Column(width="large"),
            },
        )

    with tab_users:
        st.markdown("#### Uživatelé")
        show_users_editor()
        st.markdown("#### Preautorizované e-maily")
        show_preauthorized_editor()

    with tab_challenges:
        show_db_data_editor(
            table="challenges",
            column_config={
                "points": st.column_config.NumberColumn(min_value=0),
                "category": st.column_config.SelectboxColumn(
                    options=db.get_settings_value("challenge_categories").split(","),
                ),
            },
        )

    with tab_checkpoints:
        show_db_data_editor(
            table="checkpoints",
            column_config={
                "points": st.column_config.NumberColumn(min_value=0),
                # "category": st.column_config.SelectboxColumn(
                    # options=db.get_settings_value("checkpoint_categories").split(","),
                # ),
            },
        )

    with tab_teams:
        show_db_data_editor(table="teams")

    with tab_posts:
        show_db_data_editor(
            table="posts",
            column_config={
                "action_type": st.column_config.SelectboxColumn(options=["challenge", "checkpoint", "note"]),
            },
        )

    with tab_settings:
        show_settings_editor()

    with tab_actions:
        show_actions()


def show_notifications(notifications):
    for _, notification in notifications.iterrows():
        if notification.type == "varování":
            st.warning(notification.text)
        elif notification.type == "důležité":
            st.error(notification.text)
        elif notification.type == "info" or not notification.type:
            st.info(notification.text)


def show_user_page(user, team):
    name = user["name"]
    team_name = team["team_name"] if team else "Žádný tým"

    st.markdown(f"# {name} | {team_name}")
    user, team = get_logged_info()

    if not db.is_participant(user["email"]):
        st.warning("Tento rok se X-Challenge neúčastníš.")
        st.stop()

    if not team:
        st.info("Příspěvky budeš moct přidávat po tom, co se připojíš do týmu. Informace můžeš později změnit.")
        st.markdown("### Vytvořit tým")

        show_team_info(user=user, team=team)
        st.stop()

    tab_list = ["💪 Výzva", "📍 Checkpoint", "✍️  Příspěvek", "🗺️ Poloha", "🧑‍🤝‍🧑 Tým", "👤 O mně"]
    tab_idx = 0

    notifications = db.get_table_as_df("notifications")

    if not notifications.empty:
        tab_list = ["🍍 Oznámení"] + tab_list
        tab_idx = 1

    tabs = st.tabs(tab_list)

    if not notifications.empty:
        with tabs[0]:
            show_notifications(notifications)

    with tabs[0 + tab_idx]:
        record_challenge(user)

    with tabs[1 + tab_idx]:
        record_checkpoint(user)

    with tabs[2 + tab_idx]:
        record_story(user)

    with tabs[3 + tab_idx]:
        record_location(user, team)

    with tabs[4 + tab_idx]:
        show_team_info(user, team)

    with tabs[5 + tab_idx]:
        show_user_info(user)


def main():
    authenticator, config = create_authenticator()
    tabs = None

    # delete query parameters
    st.experimental_set_query_params()

    _, center_column, _ = st.columns([1, 3, 1])

    if st.session_state["authentication_status"] == None:
        with center_column:
            tabs = st.tabs(["Přihlásit se", "Zaregistrovat se", "Reset hesla"])
            with tabs[0]:
                res = authenticator.login("Přihlásit se", "main")
            with tabs[1]:
                st.info(
                    """- **Email** použij stejný, jako jsi použil(a) pro registraci na akci. 
- **Username** je libovolný identifikátor, které budeš používat na přihlášení do systému.
- **Name** je tvoje celé jméno a příjmení.
- **Heslo** použij takové, které se ti bude dobře pamatovat, dobře psát na mobilu, a zároveň ho nenajdeš [tady](https://en.wikipedia.org/wiki/Wikipedia:10,000_most_common_passwords).
                    """
                )
                register_form(authenticator, config)

            if res[0] is not None:
                # this is necessary to display the user interface right after login and not showing all the tabs
                st.session_state["name"] = res[0]
                st.session_state["authentication_status"] = res[1]
                st.session_state["username"] = res[2]
                time.sleep(0.1)

                st.experimental_rerun()

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
        if user["role"] == "admin":
            show_admin_page()
        else:
            with center_column:
                show_user_page(user, team)

    elif st.session_state["authentication_status"] == False:
        st.error("Nesprávné přihlašovací údaje.")
        st.info("Před prvním přihlášením se musíš zaregistrovat.")
        st.session_state["authentication_status"] = None


if __name__ == "__main__":
    main()
