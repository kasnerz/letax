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

db = get_database()


def show_admin_page(user):
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
        st.caption("Databáze aktuálního ročníku X-Challenge.")
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


def action_fetch_users():
    st.caption("Načte seznam účastníků z WooCommerce")

    with st.form("fetch_wc_users"):
        product_id = st.text_input(
            "product_id", help="Číslo produktu Letní X-Challenge na webu", value=db.get_settings_value("product_id")
        )
        limit = st.number_input("limit (0 = bez omezení)", help="Maximální počet účastníků (0 = bez omezení)", value=0)

        update_submit_button = st.form_submit_button(label="Aktualizovat účastníky")

    if update_submit_button:
        if limit == 0:
            limit = None

        with st.spinner("Aktualizuji účastníky"):
            container = st.container()
            db.wc_fetch_participants(product_id=int(product_id), log_area=container, limit=limit)

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


def action_change_year():
    st.caption(
        "Změna roku založí novou databázi a skryje současné účastníky, týmy a příspěvky. Databáze ze současného roku zůstane zachována a lze se k ní vrátit."
    )

    with st.form("change_year"):
        year = st.number_input("Rok", value=int(db.get_settings_value("xchallenge_year")))
        change_year_submit_button = st.form_submit_button(label="Změnit rok")

    if change_year_submit_button:
        db.set_settings_value("xchallenge_year", year)
        return True


def action_restore_db():
    # list all the files in the "backups" folder
    backup_files = [f for f in os.listdir("backups") if os.path.isfile(os.path.join("backups", f))]

    if not backup_files:
        st.warning("Nejsou k dispozici žádné zálohy")
        st.stop()

    # sort by date
    backup_files.sort(reverse=True)

    # filename in format db_20230728163001.zip: make it more readable
    backup_files_names = [f"📁 {f[3:7]}-{f[7:9]}-{f[9:11]} {f[11:13]}:{f[13:15]}:{f[15:17]} GMT" for f in backup_files]

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


def action_set_map_link():
    with st.form("Mapa s checkpointy"):
        st.caption(
            "Odkaz na Google mapu s checkpointy ([URL pro vložení na stránky](https://www.google.com/earth/outreach/learn/visualize-your-data-on-a-custom-map-using-google-my-maps/#embed-your-map-5-5)), např. https://www.google.com/maps/d/u/0/embed?mid=1L6EC8E-uNAu4yS_Oxvymjp9FLUoTK94. Tato mapa se zobrazuje na stránce s checkpointy."
        )
        map_link = st.text_input(
            "Link:",
            value=db.get_settings_value("map_embed_url"),
            key="map_link_area",
        )

        submit_button = st.form_submit_button(label="Aktualizovat")
        container = st.empty()

    with st.expander("Náhled", expanded=True):
        if "iframe" not in map_link and "embed" in map_link:
            st.markdown(
                f"""
                <iframe
                    width="100%"
                    height="480"
                    frameborder="0" style="border:0"
                    src="{map_link}"
                    allowfullscreen>
                </iframe>
                """,
                unsafe_allow_html=True,
            )
        else:
            st.write("Mapu nelze zobrazit")

    if submit_button:
        if "iframe" in map_link:
            container.warning(
                "Je potřeba použít odkaz na vložení mapy na jiné stránky (s klíčovým slovem `embed`). Vlož jen samotnou URL (https://www.google.com/maps/d/u/0/embed?mid=<nějaký kód>) a smaž všechno kolem (včetně dalších parametrů v URL za &)."
            )
        elif "embed" not in map_link:
            container.warning(
                "Je potřeba použít odkaz na vložení mapy na jiné stránky (s klíčovým slovem `embed`). Zkus v odkazu vyměnit `edit` za `embed` a smazat všechny parametry kromě `mid=` a kódu za tím."
            )
        else:
            db.set_settings_value("map_embed_url", map_link)
            return True

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
                "👥 Načíst letošní účastníky",
                "ℹ️ Nastavit infotext",
                "📁 Obnovit zálohu databáze",
                "💻️ Systémová nastavení",
                "🗺️ Upravit mapu s checkpointy",
                "🧹 Vyčistit cache",
                "📅 Změnit aktuální ročník",
            ],
            label_visibility="hidden",
        )

        if action == "➕ Přidat extra účastníka":
            ret = action_add_participant()

        elif action == "👥 Načíst letošní účastníky":
            ret = action_fetch_users()

        elif action == "🧹 Vyčistit cache":
            ret = action_clear_cache()

        elif action == "📅 Změnit aktuální ročník":
            ret = action_change_year()

        elif action == "📁 Obnovit zálohu databáze":
            ret = action_restore_db()

        elif action == "ℹ️ Nastavit infotext":
            ret = action_set_infotext()

        elif action == "🗺️ Upravit mapu s checkpointy":
            ret = action_set_map_link()

        elif action == "💻️ Systémová nastavení":
            ret = action_set_system_settings()

    if ret is True:
        utils.clear_cache()
        st.balloons()
        time.sleep(2)
        st.experimental_rerun()


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
