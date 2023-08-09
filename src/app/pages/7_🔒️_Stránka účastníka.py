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
from unidecode import unidecode

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
    utils.clear_cache()


def reset_password_form(authenticator):
    st.info("Zadej své uživatelské jméno, nové heslo ti přijde na e-mail. Ve svém účtu ho můžeš později změnit.")
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

            utils.clear_cache()
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

    # sort checkpoints alphabetically
    checkpoints = sorted(checkpoints, key=lambda x: unidecode(x["name"].lower()))

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
        if not story_title:
            st.error("Dej příspěvku nějaký nadpis.")
            st.stop()

        if not comment:
            st.error("Dej příspěvku nějaký text.")
            st.stop()

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
    container = st.empty()
    
    with st.form("location_icon"):
        location_color = team["location_color"] or "red"
        location_icon_color = team["location_icon_color"] or "#ffffff"
        location_icon = team["location_icon"] or "user"

        # fmt: off
        icon_options = utils.get_fa_icons()
        color_options = ["red", "blue", "green", "purple", "orange", "darkred", "lightred", "beige", "darkblue", "darkgreen", "cadetblue", "darkpurple", "white", "pink", "lightblue", "lightgreen", "gray", "black", "lightgray"]
        
        location_color = st.selectbox("Barva markeru na mapě", options=color_options,  index=color_options.index(location_color))
        location_icon_color = st.color_picker("Barva ikony markeru na mapě", value=location_icon_color)
        # fmt: on
        location_icon = st.selectbox(
            "Ikona markeru na mapě (viz https://fontawesome.com/v4/icons/):",
            options=icon_options,
            index=icon_options.index(location_icon),
        )
        btn_save_options = st.form_submit_button("Uložit")

    is_visible = db.is_team_visible(team)
    st.checkbox(label="Zobrazit poslední polohu na mapě", value=is_visible, on_change=db.toggle_team_visibility, args=(team,))

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

            db.save_location(
                user, comment, longitude, latitude, accuracy, altitude, altitude_accuracy, heading, speed, date
            )
            container.success("Poloha nasdílena!")
        else:
            st.warning(
                "Nepodařilo se nasdílet polohu. Zkontroluj, jestli má tvůj prohlížeč přístup k tvé aktuální poloze."
            )
            time.sleep(5)

    if btn_save_options:
        db.save_location_options(team, location_color, location_icon_color, location_icon)
        container.success("Nastavení uloženo!")


def show_team_info(user, team):
    team_name = team["team_name"] if team else ""
    motto = team["team_motto"] if team else ""
    web = team["team_web"] if team else ""

    # all users not part of any team and not the current user
    available_paxes = db.get_available_participants(user["pax_id"], team)

    with st.form("team_info"):
        # team name
        team_name = st.text_input("Název týmu:", value=team_name)

        second_member = st.selectbox(
            "Další člen:",
            options=range(len(available_paxes)),
            format_func=lambda x: available_paxes.iloc[x]["name"],
        )
        team_motto = st.text_input("Motto týmu (nepovinné):", value=motto)
        team_web = st.text_input("Instagram, web, apod. (nepovinné):", value=web)

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
        st.cache_data.clear()
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
        st.cache_data.clear()
        st.success(f"Informace uloženy.")
        st.balloons()
        time.sleep(3)
        st.experimental_rerun()


def show_account_info(user):
    with st.form("account_info"):
        participant = db.am.get_user_by_email(user["email"])
        username = participant["username"]
        st.markdown(f"Uživatel **{username}**")
        name = st.text_input("Jméno:", value=participant["name"])

        password = st.text_input("Nové heslo:", type="password")
        password2 = st.text_input("Nové heslo znovu:", type="password")
        st.caption("Heslo vyplňuj pouze pokud ho chceš změnit.")

        submit_button = st.form_submit_button(label="Aktualizovat informace")

    # When the submit button is clicked
    if submit_button:
        if password and password2 and password != password2:
            st.error("Hesla se neshodují.")
            st.stop()

        if password:
            db.am.set_password(username, password)

        db.am.update_user_name(username, name)

        st.cache_data.clear()
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
    st.warning("Pozor: údaje upravuj pouze pokud víš, co děláš!")

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
        num_rows="dynamic",
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
        num_rows="dynamic",
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
    action = st.selectbox(
        "Akce:",
        [
            "➕ Přidat extra účastníka",
            "👥 Načíst letošní účastníky",
            "🧹 Vyčistit cache",
            "📅 Změnit aktuální ročník",
            "📁 Obnovit zálohu databáze",
        ],
        label_visibility="hidden",
    )

    if action == "👥 Načíst letošní účastníky":
        st.caption("Načte seznam účastníků z WooCommerce")

        with st.form("fetch_wc_users"):
            product_id = st.text_input(
                "product_id", help="Číslo produktu Letní X-Challenge na webu", value=db.get_settings_value("product_id")
            )
            limit = st.number_input(
                "limit (0 = bez omezení)", help="Maximální počet účastníků (0 = bez omezení)", value=0
            )

            update_submit_button = st.form_submit_button(label="Aktualizovat účastníky")

        if update_submit_button:
            if limit == 0:
                limit = None

            with st.spinner("Aktualizuji účastníky"):
                container = st.container()
                db.wc_fetch_participants(product_id=int(product_id), log_area=container, limit=limit)

            st.balloons()

    elif action == "🧹 Vyčistit cache":
        cache_btn = st.button("Vyčistit cache", on_click=utils.clear_cache)

        if cache_btn:
            st.balloons()

    elif action == "➕ Přidat extra účastníka":
        with st.form("add_extra_participant"):
            name = st.text_input("Jméno a příjmení", help="Celé jméno účastníka")
            email = st.text_input("email", help="Email účastníka")
            add_pax_submit_button = st.form_submit_button(label="Přidat účastníka")

        if add_pax_submit_button:
            if not email or not name:
                st.error("Musíš vyplnit email i jméno")
                st.stop()

            with st.spinner("Přidávám účastníka"):
                db.add_extra_participant(email=email, name=name)
                utils.clear_cache()

            st.success("Účastník přidán")
            st.balloons()

    elif action == "📅 Změnit aktuální ročník":
        st.caption(
            "Změna roku založí novou databázi a skryje současné účastníky, týmy a příspěvky. Databáze ze současného roku zůstane zachována a lze se k ní vrátit."
        )

        with st.form("change_year"):
            year = st.number_input("Rok", value=int(db.get_settings_value("xchallenge_year")))
            change_year_submit_button = st.form_submit_button(label="Změnit rok")

        if change_year_submit_button:
            db.set_settings_value("xchallenge_year", year)
            utils.clear_cache()
            st.balloons()

    elif action == "📁 Obnovit zálohu databáze":
        # list all the files in the "backups" folder
        backup_files = [f for f in os.listdir("backups") if os.path.isfile(os.path.join("backups", f))]

        if not backup_files:
            st.warning("Nejsou k dispozici žádné zálohy")
            st.stop()

        # sort by date
        backup_files.sort(reverse=True)

        # filename in format db_20230728163001.zip: make it more readable
        backup_files_names = [
            f"📁 {f[3:7]}-{f[7:9]}-{f[9:11]} {f[11:13]}:{f[13:15]}:{f[15:17]} GMT" for f in backup_files
        ]

        # selectbox
        with st.form("restore_backup"):
            backup_file = st.selectbox(
                "Záloha", backup_files, format_func=lambda x: backup_files_names[backup_files.index(x)]
            )
            restore_backup_submit_button = st.form_submit_button(label="Obnovit databázi")

        if restore_backup_submit_button:
            with st.spinner("Obnovuji databázi"):
                db.restore_backup(backup_file)

            st.success("Databáze obnovena ze zálohy.")
            st.balloons()


def show_db():
    # selectbox
    table = st.selectbox(
        "Tabulka", ["🧒 Účastníci", "🧑‍🤝‍🧑 Týmy", "🏆 Výzvy", "📍 Checkpointy", "📝 Příspěvky", "🗺️ Lokace", "🍍 Oznámení"]
    )

    if table == "🧒 Účastníci":
        show_db_data_editor(
            table="participants",
            column_config={
                "id": st.column_config.Column(width="small"),
                "email": st.column_config.Column(width="large"),
            },
        )
    elif table == "🧑‍🤝‍🧑 Týmy":
        show_db_data_editor(table="teams")

    elif table == "🏆 Výzvy":
        show_db_data_editor(
            table="challenges",
            column_config={
                "points": st.column_config.NumberColumn(min_value=0),
                "category": st.column_config.SelectboxColumn(
                    options=db.get_settings_value("challenge_categories").split(","),
                ),
            },
        )

    elif table == "📍 Checkpointy":
        show_db_data_editor(
            table="checkpoints",
            column_config={
                "points": st.column_config.NumberColumn(min_value=0),
                # "category": st.column_config.SelectboxColumn(
                # options=db.get_settings_value("checkpoint_categories").split(","),
                # ),
            },
        )

    elif table == "📝 Příspěvky":
        show_db_data_editor(
            table="posts",
            column_config={
                "action_type": st.column_config.SelectboxColumn(options=["challenge", "checkpoint", "note"]),
            },
        )

    elif table == "🗺️ Lokace":
        show_db_data_editor(table="locations")

    # elif table == "🍍 Oznámení":
    #     show_db_data_editor(
    #         table="notifications",
    #         column_config={
    #             "type": st.column_config.SelectboxColumn(options=["info", "varování", "důležité", "skryté"]),
    #         },
    #     )


def show_notification_manager():
    # TODO more user friendly
    st.markdown("#### Oznámení")

    st.caption(
        "Tato oznámení se zobrazí účastníkům na jejich stránce účastníka. Typy oznámení: info, varování, důležité, skryté."
    )

    show_db_data_editor(
        table="notifications",
        column_config={
            "type": st.column_config.SelectboxColumn(options=["info", "varování", "důležité", "skryté"]),
        },
    )


def show_admin_page():
    st.title("Administrace")

    (tab_notifications, tab_users, tab_db, tab_actions, tab_settings, tab_account) = st.tabs(
        [
            "🍍 Oznámení",
            "👤 Uživatelé",
            "✏️ Databáze",
            "🛠️ Akce",
            "⚙️ Nastavení",
            "🔑 Účet",
        ]
    )

    with tab_notifications:
        show_notification_manager()

    with tab_users:
        st.markdown("#### Uživatelé")
        show_users_editor()
        st.markdown("#### Preautorizované e-maily")
        show_preauthorized_editor()

    with tab_db:
        st.markdown("#### Databáze")
        st.caption("Databáze aktuálního ročníku X-Challenge.")
        show_db()

    with tab_settings:
        show_settings_editor()

    with tab_actions:
        show_actions()

    with tab_account:
        user = get_logged_info()[0]
        show_account_info(user)


def show_notifications(notifications):
    for _, notification in notifications.iterrows():
        if notification.type == "varování":
            st.warning(notification.text)
        elif notification.type == "důležité":
            st.error(notification.text)
        elif notification.type == "info" or not notification.type:
            st.info(notification.text)


def show_post_management(user, team):
    st.caption("Zde vidíš všechny příspěvky a polohy, které tvůj tým nasdílel. Kliknutím na tlačítko Smazat příspěvek / lokaci trvale smažeš, takže opatrně!")

    st.markdown("### Příspěvky")
    # display the list of all the posts the team posted and a "delete" button for each of them
    posts = db.get_table_as_df("posts")

    # filter posts by team
    posts = posts[posts["team_id"] == team["team_id"]]

    if posts.empty:
        st.info("Tvůj tým zatím nepřidal žádné příspěvky.")

    # keep only the columns we want to display: action_type, action_name, comment, created, files
    for i, post in posts.iterrows():
        col_type, col_name, col_desc, col_delete = st.columns([1,3,5,2])
        with col_type:
            mapping = {
                "challenge": "💪",
                "checkpoint": "📍",
                "story": "✍️",
            }
            st.write(mapping[post["action_type"]])

        with col_name:
            st.markdown("**" + post["action_name"] + "**")
        
        with col_desc:
            comment = post["comment"]
            # crop comment if too long
            if len(comment) > 100:
                comment = comment[:100] + "..."

            st.write(comment)
        
        with col_delete:
            if st.button("❌ Smazat", key=f"delete-{post['post_id']}"):
                db.delete_post(post.post_id)
                st.success("Příspěvek smazán.")
                time.sleep(2)
                st.experimental_rerun()

        st.divider()

    st.markdown("### Polohy")

    locations = db.get_table_as_df("locations")
    locations = locations[locations["team_id"] == team["team_id"]]

    if locations.empty:
        st.info("Tvůj tým zatím nenasdílel žádnou polohu.")


    for i, location in locations.iterrows():
        col_date, col_gps, col_comment, col_delete  = st.columns([3,3,5, 2])
        with col_date:
            st.markdown("**" + location["date"][:-7] + "**")
        
        with col_gps:
            gps = f'{location["latitude"]}, {location["longitude"]}'
            st.write(gps)
        
        with col_comment:
            comment = location["comment"]
            # crop comment if too long
            if len(comment) > 100:
                comment = comment[:100] + "..."

            st.write(comment)

        with col_delete:
            if st.button("❌ Smazat", key=f"delete-loc-{i}"):
                db.delete_location(location)
                st.success("Poloha smazána.")
                time.sleep(2)
                st.experimental_rerun()

        st.divider()



    

def show_user_page(user, team):
    name = user["name"]
    team_name = team["team_name"] if team else "Žádný tým"

    st.markdown(f"# {name} | {team_name}")
    user, team = get_logged_info()

    if not db.is_participant(user["email"]):
        st.warning("Tento rok se X-Challenge neúčastníš.")
        st.stop()

    if not team:
        st.info("Příspěvky budeš moct přidávat po tom, co se připojíš do týmu. Všechny informace můžeš později změnit.")
        st.markdown("### Vytvořit tým")

        show_team_info(user=user, team=team)
        st.stop()

    tab_list = ["💪 Výzva", "📍 Checkpoint", "✍️  Příspěvek", "🗺️ Poloha", "📤️ Odesláno", "🧑‍🤝‍🧑 Tým", "👤 O mně", "🔑 Účet"]
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
        show_post_management(user, team)

    with tabs[5 + tab_idx]:
        show_team_info(user, team)

    with tabs[6 + tab_idx]:
        show_user_info(user)

    with tabs[7 + tab_idx]:
        show_account_info(user)


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
