#!/usr/bin/env python3

from datetime import datetime
from streamlit_js_eval import get_geolocation
import streamlit as st
import time
import time
import traceback
import utils
import tempfile
import pandas as pd
from unidecode import unidecode
from currency_converter import CurrencyConverter


def show_user_page(db, user, team):
    name = user["name"]
    team_name = team["team_name"] if team else "Žádný tým"

    st.markdown(f"# {name} | {team_name}")
    # user, team = get_logged_info()

    if not db.is_participant(user["email"]):
        st.warning("Tento rok se X-Challenge neúčastníš.")
        st.stop()

    if not team:
        st.info(
            "Příspěvky budeš moct přidávat po tom, co se připojíš do týmu. Všechny informace můžeš později změnit."
        )
        st.markdown("### Vytvořit tým")

        show_team_info(db=db, user=user, team=team)
        st.stop()

    tab_list = [
        "🍍 Oznámení",
        "💪 Výzva",
        "📍 Checkpoint",
        "✍️  Příspěvek",
        "🗺️ Poloha",
        "🪙 Rozpočet",
        "🪂 Moje aktivita",
        "🔽 Export dat",
        "🧑‍🤝‍🧑 Tým",
        "👤 O mně",
        "🔑 Účet",
        "ℹ️ Info",
    ]

    action = st.selectbox(
        "Akce",
        tab_list,
    )

    if action == tab_list[0]:
        show_notifications(db)

    if action == tab_list[1]:
        record_challenge(db, user)

    if action == tab_list[2]:
        record_checkpoint(db, user)

    if action == tab_list[3]:
        record_story(db, user)

    if action == tab_list[4]:
        record_location(db, user, team)

    if action == tab_list[5]:
        show_budget_management(db, user, team)

    if action == tab_list[6]:
        show_post_management(db, user, team)

    if action == tab_list[7]:
        show_export_options(db, user, team)

    if action == tab_list[8]:
        show_team_info(db, user, team)

    if action == tab_list[9]:
        show_user_info(db, user)

    if action == tab_list[10]:
        show_account_info(db, user)

    if action == tab_list[11]:
        show_info_info(db)


def create_post(db, user, action_type, action, comment, files, flags=None):
    try:
        db.save_post(
            user=user,
            action_type=action_type,
            action=action,
            comment=comment,
            files=files,
            flags=flags,
        )
        st.success("Příspěvek odeslán.")
        st.balloons()
    except Exception as e:
        st.error(f"Stala se chyba: {traceback.print_exc()}")
        # print stacktrace
        traceback.print_exc()


def record_challenge(db, user):
    event = db.get_event()

    if event["status"] != "ongoing":
        st.info(
            f"Pro Letní X-Challenge {event['year']} momentálně nelze vkládat příspěvky."
        )
        return

    challenges = db.get_available_actions(user=user, action_type="challenge")

    # sort by name
    challenges = utils.sort_challenges(challenges)

    with st.form("challenge", clear_on_submit=True):
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
                db=db,
                user=user,
                action_type="challenge",
                action=challenges[challenge_idx],
                comment=comment,
                files=files,
            )
            time.sleep(2)
            st.rerun()


def record_checkpoint(db, user):
    event = db.get_event()

    if event["status"] != "ongoing":
        st.info(
            f"Pro Letní X-Challenge {event['year']} momentálně nelze vkládat příspěvky."
        )
        return

    checkpoints = db.get_available_actions(user=user, action_type="checkpoint")

    # sort checkpoints alphabetically, keep square brackets at the end
    checkpoints = sorted(
        checkpoints, key=lambda x: unidecode(x["name"].lower().replace("[", "zz"))
    )

    with st.form("checkpoint", clear_on_submit=True):
        checkpoint_idx = st.selectbox(
            "Checkpoint:",
            options=range(len(checkpoints)),
            format_func=lambda x: checkpoints[x]["name"],
        )
        challenge_completed = st.checkbox(
            "Výzva u checkpointu splněna",
            help="Zaškrtni, pokud váš tým splnil výzvu u checkpointu. Pokud má checkpoint i body za výzvu, získáš body navíc.",
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
                db=db,
                user=user,
                action_type="checkpoint",
                action=checkpoints[checkpoint_idx],
                comment=comment,
                files=files,
                flags={"checkpoint_challenge_completed": challenge_completed},
            )
            time.sleep(2)
            st.rerun()


def record_story(db, user):
    event = db.get_event()
    if event["status"] != "ongoing":
        st.info(
            f"Pro Letní X-Challenge {event['year']} momentálně nelze vkládat příspěvky."
        )
        return

    with st.form("story", clear_on_submit=True):
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
                db=db,
                user=user,
                action_type="story",
                action=story_title,
                comment=comment,
                files=files,
            )
            time.sleep(2)
            st.rerun()


def record_location(db, user, team):
    event = db.get_event()
    if event["status"] != "ongoing":
        st.info(
            f"Pro Letní X-Challenge {event['year']} momentálně nelze sdílet lokaci."
        )
        return

    # cols = st.columns(3)

    # with cols[0]:
    st.markdown("#### Sdílení polohy")

    with st.form("location", clear_on_submit=True):
        st.caption(
            "Aktuální poloha automaticky určená pomocí GPS. Funguje nejlépe když jsi venku a nedávno jsi GPS používal(a)."
        )
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

            position_manual = st.text_input("GPS pozice / přibližná adresa:")
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
                "Barva markeru na mapě",
                options=color_options,
                index=color_options.index(location_color),
                help="Seznam barev pochází odsud: github.com/lvoogdt/Leaflet.awesome-markers",
            )
            location_icon_color = st.color_picker(
                "Barva ikony markeru na mapě", value=location_icon_color
            )
            location_icon = st.selectbox(
                "Ikona markeru na mapě (viz https://fontawesome.com/search?o=a&m=free):",
                options=icon_options_list,
                index=icon_options_list.index(location_icon)
                if location_icon in icon_options_list
                else 0,
            )
            btn_save_options = st.form_submit_button("Uložit")

    container3 = st.empty()

    is_visible = db.is_team_visible(team)
    st.checkbox(
        label="Zobrazit poslední polohu na mapě",
        value=is_visible,
        on_change=db.toggle_team_visibility,
        args=(team,),
    )

    if btn_share:
        st.toast("Probíhá určování polohy...")
        location = get_geolocation(component_key="location")

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
                user,
                comment,
                longitude,
                latitude,
                accuracy,
                altitude,
                altitude_accuracy,
                heading,
                speed,
                address,
                date,
            )
            container.success("Poloha nasdílena!")
            utils.log(
                f"{team['team_name']} shared location: {address} ({latitude}, {longitude})",
                "success",
            )
        else:
            container.warning(
                "Nepodařilo se nasdílet polohu. Zkontroluj, jestli má tvůj prohlížeč přístup k tvé aktuální poloze, a zkus to prosím znovu (občas pomůže to zkusit víckrát po sobě)."
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

        db.save_location(
            user,
            comment_manual,
            longitude,
            latitude,
            None,
            None,
            None,
            None,
            None,
            address,
            date,
        )
        container2.success(
            f"Pozice nalezena: {address} ({latitude}, {longitude}).\n Poloha byla nasdílena jako aktuální v {date_str}."
        )

        utils.log(
            f"{team['team_name']} shared location manually: {address} ({latitude}, {longitude})",
            "success",
        )

    if btn_save_options:
        db.save_location_options(
            team, location_color, location_icon_color, location_icon
        )
        container3.success("Nastavení uloženo!")


def show_budget_management(db, user, team):
    event = db.get_event()
    if event["status"] != "ongoing":
        st.info(
            f"Pro Letní X-Challenge {event['year']} momentálně nelze upravovat rozpočet."
        )
        return

    budget = event.get("budget_per_person")

    if not budget:
        st.info("Pro tento ročník Letní X-Challenge není vedený rozpočet týmů.")
        return

    spending_for_team = db.get_spendings_by_team(team)

    team_members_cnt = len([x for x in db.get_team_members(team["team_id"]) if x])

    if spending_for_team.empty:
        spent = 0
    else:
        spent = spending_for_team["amount_czk"].sum()

    remaining = int(budget * team_members_cnt - spent)

    if remaining > 0:
        st.warning(f"#### 🪙 Zbývá {remaining} Kč z {budget * team_members_cnt} Kč")
    else:
        st.error(f"#### 🪙 Zbývá {remaining} Kč z {budget * team_members_cnt} Kč")

    st.markdown("#### Přidat změnu v rozpočtu")

    categories = db.get_spending_categories()
    currency_list = db.get_currency_list()

    with st.form("spending", clear_on_submit=True):
        spending_type = st.radio(
            "Typ",
            options=["Útrata", "Výdělek"],
            horizontal=True,
        )
        amount = st.number_input(
            "Částka",
            min_value=0.0,
            step=0.01,
            help="Zadej částku v původní měně. Částku můžeš zadat s přesností až na dvě desetinná místa.",
        )
        currency = st.selectbox(
            "Měna",
            options=currency_list,
            help="Pokud měna není v seznamu, přepočítej prosím částku na některou z podporovaných měn",
        )
        date = st.date_input("Datum:", value=datetime.now())
        comment = st.text_input(
            "Komentář (nepovinný):",
        )
        category = st.selectbox(
            "Kategorie",
            options=categories.keys(),
            format_func=lambda x: categories[x],
        )
        btn_submit = st.form_submit_button("Přidat útratu")

    if btn_submit:
        if amount <= 0:
            st.error("Částka musí být kladná.")
            st.stop()

        if spending_type == "Výdělek":
            amount = -amount

        db.save_spending(
            team=team,
            amount=amount,
            currency=currency,
            category=category,
            date=date,
            comment=comment,
        )
        utils.log(
            f"{team['team_name']} saved spending: {amount} {currency}",
            "success",
        )
        if amount < 0:
            st.success("Výdělek přidán.")
        else:
            st.success("Útrata přidána.")
        time.sleep(2)
        st.rerun()


def show_team_info(db, user, team):
    event = db.get_event()
    fields_disabled = event["status"] == "past"

    if fields_disabled:
        st.warning(
            f"Pro Letní X-Challenge {event['year']} momentálně nelze upravovat tým"
        )

    team_name = team["team_name"] if team else ""
    motto = team["team_motto"] if team else ""
    description = team["team_description"] if team else ""
    web = team["team_web"] if team else ""

    # all users not part of any team and not the current user
    available_paxes = db.get_available_participants(user["pax_id"], team)

    with st.form("team_info"):
        # team name
        team_name = st.text_input(
            "Název týmu:", value=team_name, disabled=fields_disabled
        )

        member2 = st.selectbox(
            "Další člen:",
            options=range(len(available_paxes)),
            format_func=lambda x: available_paxes.iloc[x]["name"],
            disabled=fields_disabled,
        )

        team_motto = st.text_input(
            "Motto týmu (nepovinné):", value=motto, disabled=fields_disabled
        )

        team_description = st.text_area(
            "O týmu (nepovinné):",
            disabled=fields_disabled,
            help="Popis, který se bude zobrazovat na stránce týmu. Můžeš využít markdown (např **tučné písmo**).",
            value=description,
        )

        team_web = st.text_input(
            "Instagram, web, apod. (nepovinné):",
            value=web,
            disabled=fields_disabled,
            help="Zadej celou URL adresu, případně Instagram handle se zavináčem na začátku. Můžeš zadat i víc handlů, stačí je oddělit čárkou.",
        )

        cols = st.columns([4, 1])
        with cols[0]:
            team_photo = st.file_uploader(
                "Týmové foto (nepovinné):", disabled=fields_disabled
            )
        with cols[1]:
            if team and team["team_photo"]:
                st.image(db.read_image(team["team_photo"], thumbnail="150_square"))
        submit_button = st.form_submit_button(
            label="Uložit tým", disabled=fields_disabled
        )

    # When the submit button is clicked
    if submit_button:
        if not team_name:
            st.error("Musíš zadat jméno týmu")
            st.stop()

        member2 = available_paxes.iloc[member2]["id"]

        # we want to keep member3 if set by administrators but we do not want to give participants a way to set it themselves
        member3 = team["member3"] if (team and ("member3" in dict(team))) else None

        db.update_or_create_team(
            team_name=team_name,
            team_motto=team_motto,
            team_description=team_description,
            team_web=team_web,
            team_photo=team_photo,
            first_member=user["pax_id"],
            second_member=member2,
            third_member=member3,
            current_team=team,
        )
        st.cache_data.clear()
        st.success(f"Tým **{team_name}** uložen.")
        st.balloons()
        time.sleep(3)
        st.rerun()


def show_user_info(db, user):
    event = db.get_event()
    fields_disabled = event["status"] == "past"

    with st.form("user_info"):
        participant = db.get_participant_by_email(user["email"])

        emergency_contact_val = participant["emergency_contact"] or ""
        bio_val = participant["bio"] or ""
        bio = st.text_area("Pár slov o mně:", value=bio_val, disabled=fields_disabled)
        emergency_contact = st.text_input(
            "Nouzový kontakt (kdo + tel. číslo; neveřejné):",
            value=emergency_contact_val,
            disabled=fields_disabled,
        )

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
        db.update_participant_info(
            username=user["username"],
            email=user["email"],
            bio=bio,
            emergency_contact=emergency_contact,
            photo=photo,
        )
        st.cache_data.clear()
        st.success(f"Informace uloženy.")
        st.balloons()
        time.sleep(3)
        st.rerun()


def show_account_info(db, user):
    authenticator = st.session_state.get("authenticator")

    with st.form("account_info"):
        participant = db.am.get_user_by_email(authenticator, user["email"])
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
            db.am.set_password(authenticator, username, password)

        db.am.update_user_name(authenticator, username, name)

        if "authenticator" in st.session_state:
            st.session_state["authenticator"].authentication_handler.credentials[
                "usernames"
            ] = db.am.accounts["credentials"]["usernames"]

        utils.clear_cache()
        st.success(f"Informace uloženy.")
        st.balloons()
        time.sleep(3)
        st.rerun()


def show_info_info(db):
    info_text = db.get_settings_value("info_text")
    st.markdown(info_text)


def show_notifications(db):
    notifications = db.get_table_as_df("notifications")

    if notifications.empty:
        st.info("Všechno je ok! Organizátoři pro tebe nemají žádné oznámení.")
        st.stop()

    for _, notification in notifications.iloc[::-1].iterrows():
        if notification.get("name"):
            txt = f"##### {notification['name']}\n{notification['text']}"
        else:
            txt = notification["text"]

        if notification.type == "varování":
            st.warning(txt)
        elif notification.type == "důležité":
            st.error(txt)
        elif notification.type == "info" or not notification.type:
            st.info(txt)


def show_posts(db, user, team, posts):
    posts = posts.to_dict("records")

    if not posts:
        st.info("Tvůj tým zatím nepřidal žádné příspěvky.")
        st.stop()

    post = st.selectbox(
        "Vyber post",
        posts,
        format_func=lambda x: f"{x['action_name']} – {x['created']}",
    )

    with st.form("post_form"):
        comment = st.text_area("Komentář", value=post["comment"])

        cols = st.columns([1, 4, 1])
        submit_button = cols[0].form_submit_button(label="💾 Uložit")
        delete_button = cols[2].form_submit_button(label="❌ Smazat")

    if submit_button:
        db.update_post_comment(post["post_id"], comment)
        st.success("Post uložen")
        time.sleep(2)
        st.rerun()

    if delete_button:
        db.delete_post(post["post_id"])
        st.success("Post smazán")
        time.sleep(2)
        st.rerun()


def show_locations(db, locations):
    locations = locations.sort_values(by="date", ascending=False)
    locations = locations.to_dict("records")

    if not locations:
        st.info("Tvůj tým zatím nenasdílel žádnou polohu.")
        st.stop()

    location = st.selectbox(
        "Vyber polohu",
        locations,
        format_func=lambda x: f"{utils.shorten_address(x['address'])} – {x['date'].split('.')[0]}",
    )

    with st.form("location_form"):
        with st.expander("Poloha na mapě"):
            location_df = pd.DataFrame([location])
            st.map(location_df, zoom=12)

        comment = st.text_area("Komentář", value=location["comment"])

        cols = st.columns([1, 4, 1])

        submit_button = cols[0].form_submit_button(label="💾 Uložit")
        delete_button = cols[2].form_submit_button(label="❌ Smazat")

    if submit_button:
        db.update_location_comment(location, comment)
        st.success("Poloha uložena")
        time.sleep(2)
        st.rerun()

    if delete_button:
        db.delete_location(location)
        st.success("Poloha smazána")
        time.sleep(2)
        st.rerun()


def show_spendings(db, spendings):
    # sort
    spending_categories = db.get_spending_categories()
    spendings = spendings.sort_values(by="date", ascending=False)

    spendings = spendings.to_dict("records")

    if not spendings:
        st.info("Transakce tvého týmu nejsou k dispozici.")
        st.stop()

    spending = st.selectbox(
        "Vyber transakci",
        spendings,
        format_func=lambda x: f"{x['date']} – {abs(x['amount'])} {x['currency']} {'(' + x['description'] + ')' if x['description'] else ''}",
    )

    with st.form("spending_form"):
        spending_type = st.radio(
            "Typ",
            options=["Útrata", "Výdělek"],
            horizontal=True,
            index=0 if spending["amount"] >= 0 else 1,
        )
        comment = st.text_area("Komentář", value=spending["description"])

        cols = st.columns([1, 4, 1])

        submit_button = cols[0].form_submit_button(label="💾 Uložit")
        delete_button = cols[2].form_submit_button(label="❌ Smazat")

    if submit_button:
        db.update_spending(spending, spending_type, comment)
        st.success("Transakce uložena")
        time.sleep(2)
        st.rerun()

    if delete_button:
        db.delete_spending(spending["id"])
        st.success("Transakce smazána")
        time.sleep(2)
        st.rerun()


def show_post_management(db, user, team):
    event = db.get_event()
    if event["status"] != "ongoing":
        st.info(
            f"Pro Letní X-Challenge {event['year']} momentálně nelze spravovat aktivitu."
        )
        return

    tab_list = ["📝 Příspěvky", "📌 Lokace", "🪙 Rozpočet"]
    tabs = st.tabs(tab_list)

    with tabs[0]:
        # display the list of all the posts the team posted and a "delete" button for each of them
        posts = db.get_posts_by_team(team["team_id"])

        if posts.empty:
            st.info("Tvůj tým zatím nepřidal žádné příspěvky.")

        else:
            show_posts(db, user, team, posts)

    with tabs[1]:
        locations = db.get_table_as_df("locations")
        locations = locations[locations["team_id"] == team["team_id"]]

        if locations.empty:
            st.info("Tvůj tým zatím nenasdílel žádnou polohu.")

        else:
            show_locations(db, locations)

    with tabs[2]:
        spendings = db.get_spendings_by_team(team)
        if (spendings is not None) and (not spendings.empty):
            show_spendings(db, spendings)
        else:
            st.info("Útraty tvého týmu nejsou k dispozici")


def show_export_options(db, user, team):
    st.markdown("#### Příspěvky")
    st.markdown(
        "Zde si můžeš vyexportovat všechny svoje příspěvky z akce (včetně fotek a videí). Pro zobrazení příspěvků ZIP archiv rozbal a otevři soubor `index.html` v prohlížeči. (Pokud máš příspěvků hodně, může to chvíli trvat.)"
    )
    export_posts_btn = st.button("📔 Exportovat příspěvky")

    if export_posts_btn:
        st.toast("Vytvářím HTML soubor...")

        with tempfile.TemporaryDirectory() as output_dir:
            xc_year = db.get_year()
            folder_name = f"letni_{xc_year}_export"

            html_zip = db.export_team_posts(
                team, output_dir, xc_year=xc_year, folder_name=folder_name
            )
            with open(html_zip, "rb") as f:
                st.download_button(
                    "🔽 Stáhnout HTML soubor",
                    f,
                    file_name=f"{folder_name}.zip",
                    mime="application/zip",
                )

    st.markdown("#### Trasa")
    st.markdown(
        "Zde si můžeš vyexportovat svoji zaznamenanou trasu ve formátu GPX. Trasu si můžeš prohlédnout například na [Google Maps](https://michaelminn.net/tutorials/google-gpx/) nebo [Mapy.cz](https://napoveda.seznam.cz/cz/mapy/nastroje/import-dat/)."
    )

    gpx_button = st.button("🗺️ Exportovat trasu")

    if gpx_button:
        gpx = db.get_locations_as_gpx(team)
        if gpx is None:
            st.info("Tvůj tým zatím nenasdílel žádnou polohu.")
        else:
            st.download_button(
                "🔽 Stáhnout GPX soubor",
                gpx,
                file_name="team_route.gpx",
                mime="text/xml",
            )
