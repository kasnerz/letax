#!/usr/bin/env python3

from database import get_database
import os
import pandas as pd
import streamlit as st
import time
import time
import utils
import re
import shutil
from zipfile import ZipFile
from user_page import show_account_info
import lxml, lxml.etree, lxml.html
from slugify import slugify


def show_admin_page(db, user):
    st.title("Administrace")

    (tab_actions, tab_users, tab_account) = st.tabs(
        [
            "👨‍🔧 Nastavení",
            "👤 Uživatelé",
            # "✏️ Databáze",
            "🔑 Účet",
        ]
    )

    # with tab_notifications:
    #     show_notification_manager(db)

    with tab_actions:
        show_actions(db)

    with tab_users:
        st.markdown("#### Uživatelé")
        st.caption(
            "Seznam užitelských účtů založených v appce. Účty s rolí 'user' lze používat na libovolnou akci, do které je uživatel přidaný jako účastník. Účty s rolí 'admin' mají přístup k administraci."
        )
        show_users_editor(db)
        st.markdown("#### Preautorizované e-maily")
        st.caption(
            "Seznam e-mailů, které se mohou registrovat do appky, aniž by byly přidány jako účastníci do aktuální akce. Nastavená role jim bude automaticky přiřazena po registraci."
        )
        show_preauthorized_editor(db)

    # with tab_db:
    #     st.markdown("#### Databáze")
    #     show_db(db)

    with tab_account:
        show_account_info(db, user)


def show_users_editor(db):
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
            "username": st.column_config.Column(disabled=True),
        },
    )
    edits = st.session_state[f"users_data_editor"]

    if any(list(edits.values())):
        db.am.save_accounts_from_df(edited_df)


def show_preauthorized_editor(db):
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


def show_db_data_editor(db, table, column_config=None):
    if (
        st.session_state.get(f"{table}_data") is None
        or st.session_state.get(f"{table}_data_editor") is None
    ):
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


def action_manage_notifications(db):
    notifications = db.get_table_as_df("notifications")

    st.markdown("#### Upravit oznámení")

    notification_list = notifications.to_dict(orient="records")
    notification_categories = ["info", "varování", "důležité", "skryté"]
    default_name = "[nové oznámení]"

    new_checkpoint = {
        "id": utils.generate_uuid(),
        "name": default_name,
        "text": "",
        "type": notification_categories[0],
    }
    notification_list.insert(0, new_checkpoint)

    for i, notification in enumerate(notification_list):
        if notification.get("name") is None:
            notification_list[i]["name"] = f"Oznámení #{i+1}"

    notification = st.selectbox(
        "Vyber oznámení",
        notification_list,
        format_func=lambda x: f"{x['name']}",
    )
    with st.form("notification_form"):
        name = st.text_input("Název", value=notification.get("name", ""))
        text = st.text_area("Text oznámení", value=notification["text"])
        category = st.selectbox(
            "Kategorie",
            notification_categories,
            index=notification_categories.index(notification["type"]),
        )
        cols = st.columns([1, 6, 1])
        submit_button = cols[0].form_submit_button(label="Uložit")
        delete_button = cols[2].form_submit_button(label="Smazat")

    if submit_button:
        if name == default_name:
            st.error(f"Název oznámení nesmí být {default_name}")
            st.stop()

        db.update_or_create_notification(
            notification_id=notification["id"],
            name=name,
            text=text,
            category=category,
        )
        st.success("Oznámení uloženo")
        return True

    if delete_button:
        if name == default_name:
            st.error("Vyber nejprve nějaké oznámení.")
            st.stop()

        db.delete_notification(notification["id"])
        st.success("Oznámení smazáno")
        return True

    st.markdown("#### Aktuální oznámení")
    st.dataframe(notifications)


def action_manage_participants(db):
    st.markdown("#### Načíst účastníky z WooCommerce")
    st.caption(
        "Zde můžeš automaticky načíst seznam přihlášených účastníků na letošní akci přes WooCommerce API."
    )

    event = db.get_event()

    if not event["product_id"]:
        st.warning(
            f'Pro ročník {event["year"]} není nastaven Wordpress product ID. Nastav ho v sekci Spravovat akce.'
        )
    else:
        with st.form("fetch_wc_users"):
            st.caption(
                f'Aktuální ročník {event["year"]}. Wordpress product ID: {event["product_id"]}'
            )
            limit = st.number_input(
                f"Načíst posledních *x* přihlášených účastníků (0 = bez omezení)",
                value=0,
            )

            update_submit_button = st.form_submit_button(label="Aktualizovat účastníky")

        if update_submit_button:
            if limit == 0:
                limit = None

            with st.spinner("Aktualizuji účastníky"):
                container = st.container()
                db.wc_fetch_participants(log_area=container, limit=limit)

    participants = db.get_table_as_df("participants")
    participants = participants.sort_values(by="name_web")
    default_name = "[nový účastník]"

    st.markdown("#### Upravit účastníka")

    participant_list = participants.to_dict(orient="records")

    new_pax = {
        "id": utils.generate_uuid(),
        "name_web": default_name,
        "email": "",
        "bio": "",
        "emergency_contact": "",
        "photo": "",
    }
    participant_list.insert(0, new_pax)

    participant = st.selectbox(
        "Vyber účastníka",
        participant_list,
        format_func=lambda x: f"{x['name_web']}",
    )
    with st.form("challenge_form"):
        name = st.text_input("Jméno a příjmení", value=participant["name_web"])
        email = st.text_input("E-mail", value=participant["email"])
        bio = st.text_input("Bio (nepovinné)", value=participant["bio"])
        emergency_contact = st.text_input(
            "Nouzový kontakt (nepovinný)", value=participant["emergency_contact"]
        )
        cols = st.columns([4, 1])
        with cols[0]:
            photo = st.file_uploader("Profilové foto (nepovinné):")
        with cols[1]:
            photo_img = participant["photo"]

            if photo_img:
                st.image(db.read_image(photo_img, thumbnail="150_square"))

        cols = st.columns([1, 6, 1])
        submit_button = cols[0].form_submit_button(label="Uložit")
        delete_button = cols[2].form_submit_button(label="Smazat")

    if submit_button:
        if name == default_name:
            st.error(f'Jméno účastníka nesmí být "{default_name}"')
            st.stop()

        if email == "":
            st.error("E-mail nesmí být prázdný")
            st.stop()

        ret = db.update_or_create_participant(
            participant_id=participant["id"],
            name=name,
            email=email,
            bio=bio,
            emergency_contact=emergency_contact,
            photo=photo,
        )
        if ret == "exists":
            st.warning("Účastník s tímto e-mailem již existuje.")
            st.stop()

        st.success("Účastník uložen")
        utils.clear_cache()
        return True

    if delete_button:
        if name == default_name:
            st.error("Vyber nejprve nějakého účastníka.")
            st.stop()

        db.delete_participant(participant["id"])
        st.success("Účastník smazán")
        return True

    st.markdown("#### Aktuální účastníci")
    st.dataframe(participants)


def action_manage_teams(db):
    teams = db.get_table_as_df("teams")

    teams = teams.sort_values(by="team_name")
    default_name = "[nový tým]"

    st.markdown("#### Upravit tým")

    team_list = teams.to_dict(orient="records")

    generated_uuid = utils.generate_uuid()
    new_team = {
        "team_id": generated_uuid,
        "team_name": default_name,
        "member1": "",
        "member2": "",
        "member3": "",
        "team_motto": "",
        "team_web": "",
        "team_photo": "",
        "is_top_x": 0,
    }
    team_list.insert(0, new_team)

    team = st.selectbox(
        "Vyber tým",
        team_list,
        format_func=lambda x: f"{x['team_name']}",
    )
    participants = db.get_participants(include_non_registered=True)

    participants = pd.concat(
        [
            pd.DataFrame(
                {
                    "id": [""],
                    "name_web": ["-"],
                }
            ),
            participants,
        ],
        ignore_index=True,
    )
    try:
        pax1_idx = int(participants[participants["id"] == team["member1"]].index[0])
        pax2_idx = int(participants[participants["id"] == team["member2"]].index[0])
        pax3_idx = int(participants[participants["id"] == team["member3"]].index[0])
    except:
        pax1_idx = 0
        pax2_idx = 0
        pax3_idx = 0

    participant_list = participants.to_dict(orient="records")

    with st.form("challenge_form"):
        name = st.text_input("Název týmu", value=team["team_name"])

        member1 = st.selectbox(
            "Člen 1",
            participant_list,
            format_func=lambda x: f"{x['name_web']}",
            index=pax1_idx,
        )
        member2 = st.selectbox(
            "Člen 2 (nepovinný)",
            participant_list,
            format_func=lambda x: f"{x['name_web']}",
            index=pax2_idx,
        )
        member3 = st.selectbox(
            "Člen 3 (nepovinný, pouze ve výjimečných případech)",
            participant_list,
            format_func=lambda x: f"{x['name_web']}",
            index=pax3_idx,
        )
        motto = st.text_input("Motto týmu (nepovinné)", value=team["team_motto"])
        web = st.text_input("Webová stránka týmu (nepovinné)", value=team["team_web"])
        is_top_x = st.checkbox("Tým je v top X", value=team["is_top_x"])

        cols = st.columns([4, 1])
        with cols[0]:
            photo = st.file_uploader("Profilové foto (nepovinné):")
        with cols[1]:
            photo_img = team["team_photo"]

            if photo_img:
                st.image(db.read_image(photo_img, thumbnail="150_square"))

        cols = st.columns([1, 6, 1])
        submit_button = cols[0].form_submit_button(label="Uložit")
        delete_button = cols[2].form_submit_button(label="Smazat")

    if submit_button:
        if name == default_name:
            st.error(f'Jméno týmu nesmí být "{default_name}"')
            st.stop()

        if member1["id"] == "":
            st.error("Vyber alespoň jednoho člena týmu.")
            st.stop()

        ret = db.update_or_create_team(
            team_name=name,
            team_motto=motto,
            team_web=web,
            team_photo=photo,
            first_member=member1["id"],
            second_member=member2["id"],
            third_member=member3["id"],
            is_top_x=is_top_x,
            current_team=team if team["team_id"] != generated_uuid else None,
        )
        st.success("Tým uložen")
        return True

    if delete_button:
        if name == default_name:
            st.error("Vyber nejprve nějaký tým.")
            st.stop()

        db.delete_team(team["team_id"])
        st.success("Tým smazán")
        return True

    st.markdown("#### Aktuální týmy")
    st.dataframe(teams)


def action_manage_challenges(db):
    challenges = db.get_table_as_df("challenges")
    challenges = challenges.sort_values(by="name")
    default_name = "[založit novou]"

    categories = db.get_challenge_categories()

    required_columns = [
        "name",
        "description",
        "category",
        "points",
    ]
    required_columns_str = ", ".join([f"`{col}`" for col in required_columns])
    st.markdown("#### Importovat výzvy")

    with st.form("import_checkpoints"):
        st.caption(
            f"Importovat můžeš výzvy ze souboru CSV nebo XLSX. Připrav soubor, který bude obsahovat sloupce: {required_columns_str}. V souboru by neměly být žádné přebytečné řádky ani sloupce. Importem se **přepíší existující výzvy**!"
        )
        uploaded_file = st.file_uploader(
            "Vyber soubor s výzvami (CSV / XLSX)",
            type=["csv", "xlsx"],
            help=f"Soubor musí obsahovat sloupce: {required_columns_str}.",
        )
        import_button = st.form_submit_button(label="Importovat")

    if import_button:
        if uploaded_file is None:
            st.error("Vyber soubor s výzvami")
            st.stop()

        if uploaded_file.type == "text/csv":
            df = pd.read_csv(uploaded_file)
        else:
            df = pd.read_excel(uploaded_file)

        for col in required_columns:
            if col not in df.columns:
                st.error(
                    f"Soubor musí obsahovat sloupec `{col}`. Nalezeno: {df.columns}. Je nadpis sloupce hned na prvním listu v prvním řádku?"
                )
                st.stop()

        # drop all rows that are completely empty
        df = df.dropna(how="all")

        # strip all whitespace for name, desciption and challenge
        df["name"] = df["name"].str.strip()
        df["description"] = df["description"].str.strip()

        for i, row in df.iterrows():
            # name, description must not be empty
            if pd.isna(row["name"]) or pd.isna(row["description"]):
                st.error(
                    f"Řádek {i+2}: Sloupce `name` a `description` nesmí být prázdné."
                )
                st.stop()

            # try to map the category to existing ones
            row_category_minimal = row["category"].lower().strip()

            for j, cat in enumerate(categories):
                cat = cat.lower()
                if row_category_minimal in cat:
                    df.at[i, "category"] = categories[j]
                    break
            else:
                st.warning(
                    f"Řádek {i+2}: Kategorii `{row['category']}` nemáme v databázi. Zkontroluj, zda je vše správně."
                )

            # if any column is empty, warn
            for col in required_columns:
                if pd.isna(row[col]):
                    st.warning(f"Řádek {i+2}: Sloupec `{col}` je prázdný, je to záměr?")

        try:
            # for points replace all NaNs with zeros
            df["points"] = df["points"].fillna(0)
            # convert all points to floats
            df["points"] = df["points"].astype(float)
        except:
            st.error(
                "Něco se nepovedlo při konverzi bodů na čísla. Zkontroluj, že všechny buňky s body obsahují platná čísla nebo jsou prázdné."
            )
            st.stop()

        with st.spinner("Importuji výzvy"):
            db.import_challenges(df)

        st.success("Výzvy importovány")
        time.sleep(2)
        st.rerun()

    st.markdown("#### Upravit výzvu")

    challenge_list = challenges.to_dict(orient="records")

    new_checkpoint = {
        "name": default_name,
        "description": "",
        "category": categories[0],
        "points": 0,
    }
    challenge_list.insert(0, new_checkpoint)

    challenge = st.selectbox(
        "Vyber výzvu",
        challenge_list,
        format_func=lambda x: f"{x['name']}",
    )
    with st.form("challenge_form"):
        name = st.text_input("Název", value=challenge["name"])
        description = st.text_area("Popis", value=challenge["description"])
        category = st.selectbox(
            "Kategorie",
            categories,
            index=categories.index(challenge["category"])
            if challenge["category"] in categories
            else 0,
        )
        points = st.number_input("Body", value=challenge["points"])

        cols = st.columns([1, 6, 1])
        submit_button = cols[0].form_submit_button(label="Uložit")
        delete_button = cols[2].form_submit_button(label="Smazat")

    if submit_button:
        if name == default_name:
            st.error(f'Název výzvy nesmí být "{default_name}"')
            st.stop()

        db.update_or_create_challenge(
            challenge_id=slugify(name),
            name=name,
            description=description,
            category=category,
            points=points,
        )
        st.success("Výzva uložena")
        return True

    if delete_button:
        if name == default_name:
            st.error("Vyber nejprve nějakou z výzev.")
            st.stop()

        db.delete_challenge(challenge["id"])
        st.success("Výzva smazána")
        return True

    st.markdown("#### Aktuální výzvy")
    st.dataframe(challenges)


def action_manage_checkpoints(db):
    checkpoints = db.get_table_as_df("checkpoints")
    checkpoints = checkpoints.sort_values(by="name")
    default_name = "[založit nový]"

    required_columns = [
        "name",
        "description",
        "challenge",
        "gps",
        "points",
        "points_challenge",
    ]
    required_columns_str = ", ".join([f"`{col}`" for col in required_columns])
    st.markdown("#### Importovat checkpointy")

    with st.form("import_checkpoints"):
        st.caption(
            f'Importovat můžeš checkpointy ze souboru CSV nebo XLSX. Připrav soubor, který bude obsahovat (hned na prvním listu v prvním řádku) sloupce: {required_columns_str}. Sloupec `gps` by měl obsahovat souřadnice ve tvaru "50.123,15.456" (s libovolným počtem desetinných míst). Souřadnice můžou být případně i součástí odkazu např. na Google Maps. V souboru by neměly být žádné přebytečné řádky ani sloupce. Importem se **přepíší existující checkpointy**!'
        )

        uploaded_file = st.file_uploader(
            "Vyber soubor s checkpointy (CSV / XLSX)",
            type=["csv", "xlsx"],
            help=f"Soubor musí obsahovat sloupce: {required_columns_str}.",
        )
        import_button = st.form_submit_button(label="Importovat")

    if import_button:
        if uploaded_file is None:
            st.error("Vyber soubor s checkpointy")
            st.stop()

        if uploaded_file.type == "text/csv":
            df = pd.read_csv(uploaded_file)
        else:
            df = pd.read_excel(uploaded_file)

        for col in required_columns:
            if col not in df.columns:
                st.error(
                    f"Soubor musí obsahovat sloupec `{col}`. Nalezeno: {df.columns}. Je nadpis sloupce hned na prvním listu v prvním řádku?"
                )
                st.stop()

        # drop all rows that are completely empty
        df = df.dropna(how="all")

        # remove any spaces in the `gps` column
        df["gps"] = df["gps"].str.replace(" ", "")

        # if any GPS coordinates are in the format "12.34N, 56.78E", convert them to "12.34, 56.78" (for W and S we need to prefix the number with a minus sign)
        df["gps"] = df["gps"].str.replace(r"(\d+\.\d+)N", r"\1", regex=True)
        df["gps"] = df["gps"].str.replace(r"(\d+\.\d+)E", r"\1", regex=True)
        df["gps"] = df["gps"].str.replace(r"(\d+\.\d+)W", r"-\1", regex=True)
        df["gps"] = df["gps"].str.replace(r"(\d+\.\d+)S", r"-\1", regex=True)

        # keep only the coordinates part of the URL if there is any
        df["gps"] = df["gps"].str.extract(r"(\d+\.\d+,-?\d+\.\d+)")

        # strip all whitespace for name, desciption and challenge
        df["name"] = df["name"].str.strip()
        df["description"] = df["description"].str.strip()
        df["challenge"] = df["challenge"].str.strip()

        for i, row in df.iterrows():
            # name, description and GPS must not be empty
            if (
                pd.isna(row["name"])
                or pd.isna(row["description"])
                or pd.isna(row["gps"])
            ):
                st.error(
                    f"Řádek {i+2}: Sloupce `name`, `description` a `gps` nesmí být prázdné."
                )
                st.stop()

            if not re.match(r"^-?\d+\.\d+,-?\d+\.\d+$", row["gps"]):
                st.error(
                    f"Řádek {i+2}: Sloupec `gps` musí obsahovat souřadnice ve tvaru '50.123, 15.456'. Nalezeno: {row['gps']}"
                )
                st.stop()

            # if any column is empty, warn
            for col in required_columns:
                if pd.isna(row[col]):
                    st.warning(f"Řádek {i+2}: Sloupec `{col}` je prázdný, je to záměr?")
        try:
            # for points replace all NaNs with zeros
            df["points"] = df["points"].fillna(0)
            df["points_challenge"] = df["points_challenge"].fillna(0)

            # convert all points and points_challenge to floats
            df["points"] = df["points"].astype(float)
            df["points_challenge"] = df["points_challenge"].astype(float)
        except:
            st.error(
                "Něco se nepovedlo při konverzi bodů na čísla. Zkontroluj, že všechny buňky s body obsahují platná čísla nebo jsou prázdné."
            )
            st.stop()

        with st.spinner("Importuji checkpointy"):
            db.import_checkpoints(df)

        st.success("Checkpointy importovány")
        time.sleep(2)
        st.rerun()

    st.markdown("#### Upravit checkpoint")

    checkpoint_list = checkpoints.to_dict(orient="records")

    new_checkpoint = {
        "id": utils.generate_uuid(),
        "name": default_name,
        "description": "",
        "challenge": "",
        "latitude": "",
        "longitude": "",
        "points": 0,
        "points_challenge": 0,
    }
    checkpoint_list.insert(0, new_checkpoint)

    checkpoint = st.selectbox(
        "Vyber checkpoint",
        checkpoint_list,
        format_func=lambda x: f"{x['name']}",
    )
    with st.form("checkpoint_form"):
        name = st.text_input("Název", value=checkpoint["name"])
        description = st.text_area("Popis", value=checkpoint["description"])
        challenge = st.text_area("Výzva", value=checkpoint["challenge"])
        lat = st.text_input("Zeměpisná šířka", value=checkpoint["latitude"])
        lon = st.text_input("Zeměpisná délka", value=checkpoint["longitude"])
        points = st.number_input("Body", value=checkpoint["points"])

        points_challenge = st.number_input(
            "Body za výzvu", value=checkpoint.get("points_challenge", 0)
        )
        cols = st.columns([1, 6, 1])
        submit_button = cols[0].form_submit_button(label="Uložit")
        delete_button = cols[2].form_submit_button(label="Smazat")

    if submit_button:
        if name == default_name:
            st.error(f'Název checkpointu nesmí být "{default_name}"')
            st.stop()
        if not re.match(r"^\d+\.\d+$", lat) or not re.match(r"^\d+\.\d+$", lon):
            st.error("Zeměpisná šířka a délka musí být ve formátu 49.123456")
            st.stop()

        db.update_or_create_checkpoint(
            checkpoint_id=checkpoint["id"],
            name=name,
            description=description,
            challenge=challenge,
            lat=lat,
            lon=lon,
            points=points,
            points_challenge=points_challenge,
        )
        st.success("Checkpoint uložen")
        return True

    if delete_button:
        if name == default_name:
            st.error("Vyber nejprve nějaký z checkpointů.")
            st.stop()

        db.delete_checkpoint(checkpoint["id"])
        st.success("Checkpoint smazán")
        return True

    st.markdown("#### Aktuální checkpointy")
    st.dataframe(checkpoints)


def action_set_events(db):
    events = db.get_events()
    active_event = db.get_active_event()

    st.markdown("#### Aktivní akce")
    with st.form("active_event_form"):
        active_event = st.selectbox(
            "Aktivní akce se zobrazuje na hlavní stránce, na stránce účastníků, a platí pro ni všechna nastavení v administraci.",
            events,
            format_func=lambda x: x["year"],
            index=events.index(active_event),
        )
        btn_active = st.form_submit_button(label="Nastavit")

    if btn_active:
        db.set_active_event(active_event["year"])
        utils.clear_cache()
        st.success("Aktivní akce nastavena")

    st.markdown("#### Nastavit akci")

    selected_event = st.selectbox(
        "Vyber ročník", events, format_func=lambda x: x["year"]
    )

    event_status = {
        "draft": "Připravovaná",
        "ongoing": "Probíhající",
        "past": "Ukončená",
    }

    with st.form("event_form"):
        event_status = st.selectbox(
            "Stav",
            list(event_status.keys()),
            format_func=lambda x: event_status[x],
            index=list(event_status.keys()).index(selected_event["status"]),
            key="event_status",
            help="Ovlivňuje zobrazení na webu.",
        )
        budget_per_person = st.number_input(
            "Rozpočet na osobu (CZK)",
            value=selected_event["budget_per_person"],
            key="event_budget",
            help="Rozpočet na osobu na akci v CZK.",
        )
        event_gmaps_url = st.text_input(
            "URL na Google Maps s checkpointy",
            value=selected_event["gmaps_url"],
            key="event_map",
            help="Odkaz na Google mapu s checkpointy ([URL pro vložení na stránky](https://www.google.com/earth/outreach/learn/visualize-your-data-on-a-custom-map-using-google-my-maps/#embed-your-map-5-5)), např. https://www.google.com/maps/d/u/0/embed?mid=1L6EC8E-uNAu4yS_Oxvymjp9FLUoTK94. Tato mapa se zobrazuje na stránce s checkpointy. Je potřeba použít odkaz na vložení mapy na jiné stránky (s klíčovým slovem `embed`). Vlož jen samotnou URL (https://www.google.com/maps/d/u/0/embed?mid=<nějaký kód>) a smaž všechno kolem (včetně dalších parametrů v URL za &).",
        )
        event_product_id = st.text_input(
            "Wordpress product ID",
            value=selected_event["product_id"],
            key="event_product_id",
            help="Číslo produktu Letní X-Challenge na webu, slouží k načtení seznamu účastníků. K nalezení ve Wordpressu na stránce s produkty.",
        )
        cols = st.columns([1, 6, 1])
        btn_save = cols[0].form_submit_button(label="Uložit")

    selected_event_id = selected_event["year"]

    if btn_save:
        db.set_event_info(
            event_id=selected_event_id,
            status=event_status,
            gmaps_url=event_gmaps_url,
            product_id=event_product_id,
            budget_per_person=budget_per_person,
        )
        utils.clear_cache()
        st.success("Nastavení uloženo.")

    st.markdown("#### Založit novou akci")

    with st.form("add_event_form"):
        new_year = st.text_input("Rok (např. 2024)", key="add_event_year")
        btn_add = st.form_submit_button(label="Založit akci")

    if btn_add:
        # refuse to have two events with the same year
        for event in events:
            if event["year"] == new_year:
                st.error("Tento ročník již existuje.")
                st.stop()

        db.create_new_event(year=new_year)
        st.success(
            "Akce přidána jako připravovaná. Nezapomeň akci nastavit jako probíhající!"
        )
        st.balloons()
        time.sleep(2)
        utils.clear_cache()
        st.rerun()


def export_full_website(events, output_dir):
    os.makedirs(output_dir, exist_ok=True)

    with open("static/website_export/base.html") as f:
        base_html = f.read()

    base_html = lxml.html.fromstring(base_html)
    event_list_element = base_html.xpath('//div[@id="event-list"]')[0]
    # event_list_element.clear()
    for i, event in enumerate(events):
        if event["status"] == "draft":
            continue
        a = lxml.etree.Element("a", href=f"{event['year']}/index.html")
        a.text = event["year"]
        event_list_element.append(a)

        if i < len(events) - 1:
            # insert br
            event_list_element.append(lxml.etree.Element("br"))

    base_html = lxml.html.tostring(base_html).decode("utf-8")
    shutil.copy("static/logo.png", os.path.join(output_dir, "logo.png"))

    with open(os.path.join(output_dir, "index.html"), "w") as f:
        f.write(base_html)

    for event in events:
        if event["status"] == "draft":
            continue

        st.write(f"Exportuji {event['year']}")
        db_event = get_database(event_id=event["year"])
        db_event.export_static_website(output_dir=output_dir)


def action_export(db):
    events = db.get_events()
    st.caption(
        "Zde je možné stáhnout statickou verzi webu a aktualizovat web na [letni.x-challenge.cz](https://letni.x-challenge.cz)."
    )
    btn_export = st.button(label="Stáhnout export lokálně")
    btn_ftp = st.button(
        label="Aktualizovat letni.x-challenge.cz",
        help="Vyexportuje statickou verzi webu na letni.x-challenge.cz",
    )
    # important to keep the trailing slash
    output_dir = "static/website_export/export/"

    if btn_ftp:
        with st.status("Exportuji web"):
            export_full_website(events=events, output_dir=output_dir)

        with st.spinner("Aktualizuji web letni.x-challenge.cz, čekej prosím..."):
            # upload to FTP
            utils.upload_to_ftp(
                local_dir=output_dir,
                remote_dir="www/subdom/letni",
            )

        utils.log(
            f"Exported static website to HTML and uploaded to FTP",
            level="success",
        )
        st.success("Web aktualizován.")
        st.balloons()

    if btn_export:
        with st.status("Exportuji web"):
            export_full_website(events=events, output_dir=output_dir)
            tmp_filename = f"xc_export.zip"

            with ZipFile(os.path.join(output_dir, tmp_filename), "w") as zip_file:
                for root, _, files in os.walk(output_dir):
                    for file in files:
                        if file != tmp_filename:  # Exclude the zip file itself
                            file_path = os.path.join(root, file)
                            archive_name = os.path.relpath(file_path, output_dir)
                            archive_name = os.path.join(f"web", archive_name)
                            zip_file.write(file_path, archive_name)

        utils.log(
            f"Exported static website to HTML",
            level="success",
        )
        with open(os.path.join(output_dir, tmp_filename), "rb") as f:
            st.download_button(
                "🔽 Stáhnout export webu",
                f,
                file_name=tmp_filename,
                mime="application/zip",
            )
        # remove temporary folder
        shutil.rmtree(output_dir)


def action_restore_db(db):
    os.makedirs("backups", exist_ok=True)

    # list all the files in the "backups" folder
    backup_files = [
        f for f in os.listdir("backups") if os.path.isfile(os.path.join("backups", f))
    ]

    if not backup_files:
        st.warning("Nejsou k dispozici žádné zálohy")
        st.stop()

    # sort by date
    backup_files.sort(reverse=True)

    # filename in format db_20230728163001.zip: make it more readable
    backup_files_names = [
        f"📁 {f[3:7]}-{f[7:9]}-{f[9:11]} {f[11:13]}:{f[13:15]}:{f[15:17]} GMT"
        for f in backup_files
    ]

    # selectbox
    with st.form("restore_backup"):
        backup_file = st.selectbox(
            "Záloha",
            backup_files,
            format_func=lambda x: backup_files_names[backup_files.index(x)],
        )
        restore_backup_submit_button = st.form_submit_button(label="Obnovit databázi")

    if restore_backup_submit_button:
        with st.spinner("Obnovuji databázi"):
            db.restore_backup(backup_file)

        st.success("Databáze obnovena ze zálohy.")
        return True


def action_set_infotext(db):
    with st.form("Info stránka"):
        info_text = st.text_area(
            "Text na info stránce (pro zvýraznění můžeš využít [Markdown](https://www.markdownguide.org/cheat-sheet/)):",
            value=db.get_settings_value("info_text"),
        )

        submit_button = st.form_submit_button(label="Aktualizovat")

    with st.expander("Náhled", expanded=True):
        st.markdown(info_text)

    if submit_button:
        db.set_settings_value("info_text", info_text)
        return True


def action_set_awards(db):
    teams = sorted(
        db.get_teams().to_dict(orient="records"), key=lambda x: x["team_name"]
    )
    st.caption(
        "Zde můžeš nastavit výherce soutěže, kteří budou vidět na hlavní straně."
    )
    teams_select = st.selectbox(
        "Tým",
        teams,
        format_func=lambda x: x["team_name"],
    )
    if teams_select is None:
        st.warning("Zatím nemáme žádné týmy")
        st.stop()

    with st.form("Ocenění"):
        info_text = st.text_input(
            'Nastavit týmové ocenění (např. "Sebepřekonání")',
            value=teams_select["award"],
        )

        submit_button = st.form_submit_button(label="Nastavit")

    if submit_button:
        db.set_team_award(teams_select["team_id"], info_text)
        st.balloons()
        st.success("Ocenění nastaveno")

    st.markdown("#### Aktuální výherci")
    best_teams = db.get_teams_with_awards()
    # select only `team_name` and `award` columns
    best_teams = best_teams[["team_name", "award"]]
    st.dataframe(best_teams)


def action_set_system_settings(db):
    st.markdown("#### Exportovat web")
    action_export(db)

    st.markdown("#### Vyčistit cache")
    st.caption(
        "Vyčistit cache může pomoci v případě, že se některé údaje v appce (například uživatelské účty) nedaří aktualizovat."
    )
    cache_btn = st.button("Vyčistit cache", on_click=utils.clear_cache)

    if cache_btn:
        return True

    st.markdown("#### Obnovit databázi ze zálohy")
    action_restore_db(db)

    st.markdown("#### Nastavení souborového systému")

    st.caption(
        "Zde můžeš nastavit, zda se mají soubory ukládat na lokální disk nebo do AWS S3."
    )
    with st.form("Filesystem:"):
        filesystem = st.selectbox(
            "Filesystém",
            ["local", "s3"],
            index=["local", "s3"].index(db.get_settings_value("file_system")),
        )
        s3_bucket = st.text_input(
            "S3 Bucket",
            value=db.get_settings_value("fs_bucket"),
        )
        submit_button_filesystem = st.form_submit_button(label="Nastavit")

    if submit_button_filesystem:
        db.set_settings_value("file_system", filesystem)
        db.set_settings_value("fs_bucket", s3_bucket)
        return True


def show_actions(db):
    cols = st.columns([2, 1])

    with cols[0]:
        action = st.selectbox(
            "Akce:",
            [
                "🍍 Oznámení",
                "📅 Akce",
                "💪 Výzvy",
                "📌 Checkpointy",
                "🧑 Účastníci",
                "🧑‍🤝‍🧑 Týmy",
                "ℹ️ Infotext",
                "🏆️ Výherci",
                "💻️ Pokročilá nastavení",
            ],
            label_visibility="hidden",
        )

        if action == "📅 Akce":
            ret = action_set_events(db)

        elif action == "💪 Výzvy":
            ret = action_manage_challenges(db)

        elif action == "📌 Checkpointy":
            ret = action_manage_checkpoints(db)

        elif action == "🍍 Oznámení":
            ret = action_manage_notifications(db)

        elif action == "🧑 Účastníci":
            ret = action_manage_participants(db)

        elif action == "🧑‍🤝‍🧑 Týmy":
            ret = action_manage_teams(db)

        elif action == "🏆️ Výherci":
            ret = action_set_awards(db)

        elif action == "ℹ️ Infotext":
            ret = action_set_infotext(db)

        elif action == "💻️ Pokročilá nastavení":
            ret = action_set_system_settings(db)

    if ret is True:
        utils.clear_cache()
        st.balloons()
        time.sleep(2)
        st.rerun()


# def show_db(db):
#     # selectbox
#     table = st.selectbox(
#         "Tabulka",
#         [
#             "🧒 Účastníci",
#             "🧑‍🤝‍🧑 Týmy",
#             "🏆 Výzvy",
#             "📍 Checkpointy",
#             "📝 Příspěvky",
#             "🗺️ Lokace",
#             "🍍 Oznámení",
#         ],
#     )

#     if table == "🧒 Účastníci":
#         show_db_data_editor(
#             db=db,
#             table="participants",
#             column_config={
#                 "id": st.column_config.Column(width="small"),
#                 "email": st.column_config.Column(width="large"),
#             },
#         )
#     elif table == "🧑‍🤝‍🧑 Týmy":
#         show_db_data_editor(db=db, table="teams")

#     elif table == "🏆 Výzvy":
#         pass
#         # 🌞 denní výzva
#         # 🤗 lidská interakce
#         # 💙 zlepšení světa
#         # 👣 dobrodružství
#         # 🏋️ fyzické překonání
#         # 📝 reportování
#         # 🧘 nitrozpyt
#         # show_db_data_editor(
#         #     db=db,
#         #     table="challenges",
#         #     column_config={
#         #         "points": st.column_config.NumberColumn(min_value=0),
#         #         "category": st.column_config.SelectboxColumn(
#         #             options=db.get_settings_value("challenge_categories"),
#         #         ),
#         #     },
#         # )

#     elif table == "📍 Checkpointy":
#         show_db_data_editor(
#             db=db,
#             table="checkpoints",
#             column_config={
#                 "points": st.column_config.NumberColumn(min_value=0),
#             },
#         )

#     elif table == "📝 Příspěvky":
#         show_db_data_editor(
#             db=db,
#             table="posts",
#             column_config={
#                 "action_type": st.column_config.SelectboxColumn(
#                     options=["challenge", "checkpoint", "note"]
#                 ),
#             },
#         )

#     elif table == "🗺️ Lokace":
#         show_db_data_editor(db=db, table="locations")


# def show_notification_manager(db):
#     # TODO more user friendly
#     st.markdown("#### Oznámení")

#     st.caption(
#         "Tato oznámení se zobrazí účastníkům na jejich stránce účastníka. Typy oznámení: info, varování, důležité, skryté."
#     )

#     show_db_data_editor(
#         db=db,
#         table="notifications",
#         column_config={
#             "type": st.column_config.SelectboxColumn(
#                 options=["info", "varování", "důležité", "skryté"]
#             ),
#         },
#     )
