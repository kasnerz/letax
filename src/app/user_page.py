#!/usr/bin/env python3

from database import get_database
from datetime import datetime
from streamlit_js_eval import get_geolocation
import streamlit as st
import time
import time
import traceback
import utils
from unidecode import unidecode


db = get_database()


def show_user_page(user, team):
    name = user["name"]
    team_name = team["team_name"] if team else "Žádný tým"

    st.markdown(f"# {name} | {team_name}")
    # user, team = get_logged_info()

    if not db.is_participant(user["email"]):
        st.warning("Tento rok se X-Challenge neúčastníš.")
        st.stop()

    if not team:
        st.info("Příspěvky budeš moct přidávat po tom, co se připojíš do týmu. Všechny informace můžeš později změnit.")
        st.markdown("### Vytvořit tým")

        show_team_info(user=user, team=team)
        st.stop()

    tab_list = [
        "💪 Výzva",
        "📍 Checkpoint",
        "✍️  Příspěvek",
        "🗺️ Poloha",
        "📤️ Odesláno",
        "🧑‍🤝‍🧑 Tým",
        "👤 O mně",
        "🔑 Účet",
        "ℹ️ Info",
    ]
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

    with tabs[8 + tab_idx]:
        show_info_info()


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

    # sort by name
    challenges = utils.sort_challenges(challenges)

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
        st.caption("Aktuální poloha pomocí GPS pozice.")
        comment = st.text_input(
            "Komentář:",
        )
        btn_share = st.form_submit_button("📌 Zaznamenat polohu")
    container = st.empty()

    with st.expander("🌐 Zadat polohu ručně"):
        with st.form("location_manual"):
            st.caption(
                "Zde můžeš zadat polohu v určitém čase zpětně. Zadej buď GPS pozici nebo adresu (stačí např. '<město>, <země>')."
            )
            cols = st.columns(2)

            datetime_now = datetime.now()
            datetime_now = utils.convert_datetime_server_to_prague(datetime_now)

            with cols[0]:
                date_manual = st.date_input("Datum:", value=datetime_now.date())
            with cols[1]:
                time_manual = st.time_input("Čas (UTC+2):", value=datetime_now.time())

            position_manual = st.text_input("GPS pozice / adresa:")
            comment_manual = st.text_input(
                "Komentář:",
            )
            btn_share_manual = st.form_submit_button("🌐 Zadat polohu ručně")

    container2 = st.empty()

    with st.expander("🔧 Nastavení ikony na mapě"):
        with st.form("location_icon"):
            location_color = team["location_color"] or "red"
            location_icon_color = team["location_icon_color"] or "#ffffff"
            location_icon = team["location_icon"] or "user"

            icon_options = db.get_fa_icons()
            icon_options_list = sorted(list(icon_options.keys()))

            # fmt: off
            color_options = [ "red", "blue", "green", "purple", "orange", "darkred", "lightred", "beige", "darkblue", "darkgreen", "cadetblue", "darkpurple", "white", "pink", "lightblue", "lightgreen", "gray", "black", "lightgray", ]
            # fmt: on

            location_color = st.selectbox(
                "Barva markeru na mapě", options=color_options, index=color_options.index(location_color)
            )
            location_icon_color = st.color_picker("Barva ikony markeru na mapě", value=location_icon_color)
            location_icon = st.selectbox(
                "Ikona markeru na mapě (viz https://fontawesome.com/search?o=a&m=free):",
                options=icon_options_list,
                index=icon_options_list.index(location_icon) if location_icon in icon_options_list else 0,
            )
            btn_save_options = st.form_submit_button("Uložit")

    container3 = st.empty()

    is_visible = db.is_team_visible(team)
    st.checkbox(
        label="Zobrazit poslední polohu na mapě", value=is_visible, on_change=db.toggle_team_visibility, args=(team,)
    )

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
            address = db.get_address(latitude, longitude)

            db.save_location(
                user, comment, longitude, latitude, accuracy, altitude, altitude_accuracy, heading, speed, address, date
            )
            container.success("Poloha nasdílena!")
            utils.log(f"{team['team_name']} shared location: {address} ({latitude}, {longitude})", "success")
        else:
            container.warning(
                "Nepodařilo se nasdílet polohu. Zkontroluj, jestli má tvůj prohlížeč přístup k tvé aktuální poloze, a zkus to prosím znovu."
            )
            time.sleep(5)

    if btn_share_manual:
        if not position_manual:
            container2.error("Zadej GPS pozici nebo adresu.")
            st.stop()

        position = db.parse_position(position_manual)

        if not position:
            container2.warning(
                f"Zadaný vstup '{position_manual}' se nepodařilo naparsovat na polohu. Zkus ho prosím přeformulovat např. na '50.123456, 14.123456' nebo 'Praha'."
            )
            st.stop()

        longitude = position.longitude
        latitude = position.latitude
        address = position.address

        date = datetime.combine(date_manual, time_manual)
        date_str = date.strftime("%d.%m.%Y %H:%M")
        date = utils.convert_datetime_prague_to_server(date)

        # if date is in the future, refuse
        # note that server is in GMT timezone and we are in UTC+2
        if date > datetime.now():
            container2.error("Cestování v čase zatím nepodporujeme :)")
            st.stop()

        db.save_location(user, comment_manual, longitude, latitude, None, None, None, None, None, address, date)
        container2.success(
            f"Pozice nalezena: {address} ({latitude}, {longitude}).\n Poloha byla nasdílena jako aktuální v {date_str}."
        )

        utils.log(f"{team['team_name']} shared location manually: {address} ({latitude}, {longitude})", "success")

    if btn_save_options:
        db.save_location_options(team, location_color, location_icon_color, location_icon)
        container3.success("Nastavení uloženo!")


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
                st.image(db.read_image(team["team_photo"], thumbnail="150_square"))
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
                st.image(db.read_image(photo_img, thumbnail="150_square"))

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


def show_info_info():
    info_text = db.get_settings_value("info_text")
    st.markdown(info_text)


def show_notifications(notifications):
    for _, notification in notifications.iterrows():
        if notification.type == "varování":
            st.warning(notification.text)
        elif notification.type == "důležité":
            st.error(notification.text)
        elif notification.type == "info" or not notification.type:
            st.info(notification.text)


def show_post_management(user, team):
    st.caption(
        "Zde vidíš všechny příspěvky a polohy, které tvůj tým nasdílel. Kliknutím na tlačítko Smazat příspěvek / lokaci trvale smažeš, takže opatrně!"
    )
    st.markdown("### Příspěvky")
    # display the list of all the posts the team posted and a "delete" button for each of them
    posts = db.get_posts_by_team(team["team_id"])

    if posts.empty:
        st.info("Tvůj tým zatím nepřidal žádné příspěvky.")

    # keep only the columns we want to display: action_type, action_name, comment, created, files
    for i, post in posts.iterrows():
        col_type, col_name, col_desc, col_delete = st.columns([1, 3, 5, 2])
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
                utils.log(
                    f"Team {team['team_name']} deleted post {post['post_id']}: {post['action_name']}", level="info"
                )
                time.sleep(2)
                st.experimental_rerun()

        st.divider()

    st.markdown("### Polohy")

    locations = db.get_table_as_df("locations")
    locations = locations[locations["team_id"] == team["team_id"]]

    if locations.empty:
        st.info("Tvůj tým zatím nenasdílel žádnou polohu.")

    # sort
    locations = locations.sort_values(by="date", ascending=False)

    for i, location in locations.iterrows():
        col_date, col_gps, col_delete = st.columns([3, 5, 3])
        with col_date:
            date = utils.get_readable_datetime(location["date"])
            st.markdown("**" + date + "**")

            comment = location["comment"]
            # crop comment if too long
            if len(comment) > 100:
                comment = comment[:100] + "..."

            st.write(comment)

        with col_gps:
            gps = f'{location["address"]} ({location["latitude"]}, {location["longitude"]})'
            st.write(gps)

        with col_delete:
            if st.button("❌ Smazat", key=f"delete-loc-{i}"):
                db.delete_location(location)
                st.success("Poloha smazána.")
                time.sleep(2)
                st.experimental_rerun()

        st.divider()
