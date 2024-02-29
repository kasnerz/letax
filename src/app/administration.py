#!/usr/bin/env python3

from database import get_database
import os
import pandas as pd
import streamlit as st
import time
import time
import utils
import re
from user_page import show_account_info

print("Admin top")
params = st.query_params
event_id = utils.get_event_id(params)
db = get_database(event_id=event_id)


def show_admin_page(user):
    print("Admin inner")
    params = st.query_params
    event_id = utils.get_event_id(params)
    db = get_database(event_id=event_id)
    st.session_state["event"] = db.get_event()

    st.title("Administrace")

    (tab_notifications, tab_users, tab_db, tab_actions, tab_account) = st.tabs(
        [
            "🍍 Oznámení",
            "👤 Uživatelé",
            "✏️ Databáze",
            "⚙️ Akce a nastavení",
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
        show_db()

    with tab_actions:
        show_actions()

    with tab_account:
        show_account_info(user)


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
            "username": st.column_config.Column(disabled=True),
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


def action_fetch_users():
    st.caption(
        "Automaticky načte seznam přihlášených účastníků přes WooCommerce API. Účastníky lze přidat i manuálně přes Přidat extra účastníka."
    )

    with st.form("fetch_wc_users"):
        limit = st.number_input(
            "limit (0 = bez omezení)",
            help="Maximální počet účastníků (0 = bez omezení)",
            value=0,
        )

        update_submit_button = st.form_submit_button(label="Aktualizovat účastníky")

    event = db.get_event()
    if event["product_id"] is None:
        st.error(
            "Není nastaven Wordpress product ID. Nastav ho v sekci Spravovaat akce."
        )
        st.stop()

    if update_submit_button:
        if limit == 0:
            limit = None

        with st.spinner("Aktualizuji účastníky"):
            container = st.container()
            db.wc_fetch_participants(log_area=container, limit=limit)

        return True


def action_clear_cache():
    cache_btn = st.button("Vyčistit cache", on_click=utils.clear_cache)

    if cache_btn:
        return True


def action_add_participant():
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
        return True


def action_set_events():
    events = db.get_events()
    st.markdown("#### Nastavit akci")

    selected_event = st.selectbox(
        "Vyber ročník", events, format_func=lambda x: x["year"]
    )

    with st.form("event_form"):
        event_status_idx = ["active", "draft", "past"].index(selected_event["status"])
        event_status = st.selectbox(
            "Status",
            options=["active", "draft", "past"],
            key="event_status",
            help="Aktivní akce se zobrazuje na hlavní stránce. Draft se zobrazuje jen administrátorům. Past se zobrazuje v archivu.",
            index=event_status_idx,
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

    selected_event_id = selected_event["id"]

    if btn_save:
        # refuse to set two active events
        if event_status == "active":
            for event in events:
                if event["status"] == "active" and event["id"] != selected_event_id:
                    st.error(
                        "Nelze nastavit dvě aktivní akce. Nejdřív nastav tu starou jako draft nebo past."
                    )
                    st.stop()

        db.set_event_info(
            event_id=selected_event_id,
            status=event_status,
            gmaps_url=event_gmaps_url,
            product_id=event_product_id,
        )
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
        st.success("Akce přidána. Nezapomeň akci nastavit jako aktivní!")
        st.balloons()
        time.sleep(2)
        st.rerun()


def action_restore_db():
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


def action_set_infotext():
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


def action_set_awards():
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


def action_set_system_settings():
    with st.form("Kategorie výzev:"):
        challenge_categories = st.text_area(
            "Kategorie výzev (1 kategorie na řádek):",
            value="\n".join(db.get_settings_value("challenge_categories")),
        )
        submit_button_categories = st.form_submit_button(label="Nastavit")

    if submit_button_categories:
        challenge_categories = challenge_categories.split("\n")
        db.set_settings_value("challenge_categories", challenge_categories)
        return True

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


def show_actions():
    cols = st.columns([2, 1])

    with cols[0]:
        action = st.selectbox(
            "Akce:",
            [
                "➕ Přidat extra účastníka",
                "👥 Načíst účastníky z Wordpressu",
                "ℹ️ Nastavit infotext",
                "📅 Spravovat akce",
                "🏆️ Nastavit výherce",
                "🧹 Vyčistit cache",
                "📁 Obnovit zálohu databáze",
                "💻️ Pokročilá nastavení",
            ],
            label_visibility="hidden",
        )

        if action == "➕ Přidat extra účastníka":
            ret = action_add_participant()

        elif action == "👥 Načíst účastníky z Wordpressu":
            ret = action_fetch_users()

        elif action == "🏆️ Nastavit výherce":
            ret = action_set_awards()

        elif action == "🧹 Vyčistit cache":
            ret = action_clear_cache()

        elif action == "📅 Spravovat akce":
            ret = action_set_events()

        elif action == "📁 Obnovit zálohu databáze":
            ret = action_restore_db()

        elif action == "ℹ️ Nastavit infotext":
            ret = action_set_infotext()

        elif action == "💻️ Pokročilá nastavení":
            ret = action_set_system_settings()

    if ret is True:
        utils.clear_cache()
        st.balloons()
        time.sleep(2)
        st.rerun()


def show_db():
    # selectbox
    table = st.selectbox(
        "Tabulka",
        [
            "🧒 Účastníci",
            "🧑‍🤝‍🧑 Týmy",
            "🏆 Výzvy",
            "📍 Checkpointy",
            "📝 Příspěvky",
            "🗺️ Lokace",
            "🍍 Oznámení",
        ],
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
                    options=db.get_settings_value("challenge_categories"),
                ),
            },
        )

    elif table == "📍 Checkpointy":
        show_db_data_editor(
            table="checkpoints",
            column_config={
                "points": st.column_config.NumberColumn(min_value=0),
            },
        )

    elif table == "📝 Příspěvky":
        show_db_data_editor(
            table="posts",
            column_config={
                "action_type": st.column_config.SelectboxColumn(
                    options=["challenge", "checkpoint", "note"]
                ),
            },
        )

    elif table == "🗺️ Lokace":
        show_db_data_editor(table="locations")


def show_notification_manager():
    # TODO more user friendly
    st.markdown("#### Oznámení")

    st.caption(
        "Tato oznámení se zobrazí účastníkům na jejich stránce účastníka. Typy oznámení: info, varování, důležité, skryté."
    )

    show_db_data_editor(
        table="notifications",
        column_config={
            "type": st.column_config.SelectboxColumn(
                options=["info", "varování", "důležité", "skryté"]
            ),
        },
    )
