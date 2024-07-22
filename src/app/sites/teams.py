#!/usr/bin/env python3

import streamlit as st
import streamlit_authenticator as stauth
import os
import time
import yaml
from yaml.loader import SafeLoader
import time
import pandas as pd
from database import get_database
import accounts
import utils
import re
from unidecode import unidecode
import folium
from streamlit_folium import st_folium, folium_static

st.set_page_config(page_title="Týmy", page_icon="static/favicon.png", layout="wide")

params = st.query_params
event_id = utils.get_event_id(params)

db = get_database(event_id=event_id)
st.session_state["event"] = db.get_event()
st.session_state["active_event"] = db.get_active_event()
utils.page_wrapper()


def backbtn():
    st.query_params.clear()


def parse_links(web):
    if web.startswith("http"):
        return web

    if web.startswith("www"):
        return f"https://{web}"

    # some people post just instagram handles - find all handles and add https://instagram.com/ in front of them

    # find all handles
    handles = re.findall(r"@(\w+)", web)

    if not handles:
        return web

    links = []
    for handle in handles:
        # name = handle.group(1)
        links.append(f"[@{handle}](https://instagram.com/{handle})")

    return ", ".join(links)


def get_pax_link(pax_id, pax_name):
    return f"<a href='/Účastníci?id={pax_id}' target='_self' class='app-link' margin-top: -10px;'>{pax_name}</a>"


def show_profile(team_id):
    st.button("← Týmy", on_click=backbtn)

    team = db.get_team_by_id(team_id)

    if not team:
        st.error("Tým nebyl nalezen.")
        st.stop()

    columns = st.columns([1, 3, 2], gap="large")

    with columns[1]:
        st.markdown(f"<h2>{db.get_team_link(team)}</h2>", unsafe_allow_html=True)

        member_1 = db.get_participant_by_id(team["member1"])
        member_string = get_pax_link(team["member1"], member_1["name"])

        if team["member2"]:
            member_2 = db.get_participant_by_id(team["member2"])
            member_string += ", "
            member_string += get_pax_link(team["member2"], member_2["name"])

        if team["member3"]:
            member_3 = db.get_participant_by_id(team["member3"])
            member_string += ", "
            member_string += get_pax_link(team["member3"], member_3["name"])

        st.markdown(f"<h5>{member_string}</h5>", unsafe_allow_html=True)

        if team["team_motto"]:
            st.write(f"{team['team_motto']}")

        if team["team_web"]:
            links = parse_links(team["team_web"])
            st.markdown(f"🔗 {links}")

        posts = db.get_posts_by_team(team_id)
        st.divider()
        st.write("#### Příspěvky")

        if posts.empty:
            st.info("Tým nemá žádné příspěvky.")
        else:
            for i, post in posts.iterrows():
                # link to post
                post_link = f"/Příspěvky?post={post['post_id']}&event_id={event_id}"
                post_date = pd.to_datetime(post["created"]).strftime("%d.%m.%Y %H:%M")
                st.markdown(
                    f"{post_date} – <b><a href='{post_link}' target='_self'> {post['action_name']}</a><b>",
                    unsafe_allow_html=True,
                )

        st.write("#### Trasa")
        team_locations = db.get_table_as_df("locations")
        team_locations = team_locations[team_locations["team_id"] == team_id]

        if team_locations.empty:
            st.info("Tým nemá žádné záznamy v mapě.")
        else:
            with st.expander("Zobrazit na mapě"):
                m = folium.Map(
                    location=[
                        team_locations.latitude.mean(),
                        team_locations.longitude.mean(),
                    ],
                    zoom_start=4,
                )
                # folium.TileLayer("").add_to(m)

                for _, location in team_locations.iterrows():
                    team = db.get_team_by_id(location["team_id"])
                    team_icon = team["location_icon"] or "user"
                    team_color = team["location_color"] or "red"
                    team_icon_color = team["location_icon_color"] or "white"

                    team_name = team["team_name"]
                    date = location["date"]
                    ago_str = utils.ago(date)
                    # ago_str = date

                    text = "<b>" + team_name + "</b>"

                    if location["comment"]:
                        popup = f"{location['comment']}<br><br>"
                    else:
                        popup = ""

                    popup += f"<i>{ago_str}</i>"

                    icons = db.get_fa_icons()
                    icon_type = icons.get(team_icon, "fa-solid")

                    folium.Marker(
                        [location["latitude"], location["longitude"]],
                        popup=popup,
                        tooltip=text,
                        icon=folium.Icon(
                            color=team_color,
                            icon=f"{icon_type} fa-{team_icon}",
                            icon_color=team_icon_color,
                            prefix="fa",
                        ),
                    ).add_to(m)

                # draw lines between the locations
                locations = team_locations[["latitude", "longitude"]].values.tolist()

                folium.PolyLine(
                    locations, color=team_color, weight=2.5, opacity=1
                ).add_to(m)

                folium_static(m, width=None, height=500)

        with columns[2]:
            photo_path = team["team_photo"]
            if photo_path:
                st.image(db.read_image(photo_path, thumbnail="1000"))
            else:
                st.image("static/team.png")


def get_member_link(member_id, member_name):
    return f"<a href='/Účastníci?id={member_id}&event_id={event_id}' class='app-link' target='_self'>{member_name}</a>"


# @st.cache_data(show_spinner=False)
def show_teams():
    teams = db.get_teams()

    if teams.empty:
        st.info("Zatím nemáme žádné týmy. Přihlas se a založ si svůj!")
        st.stop()

    # considering unicode characters in Czech alphabet
    teams = teams.sort_values(
        by="team_name", key=lambda x: [unidecode(a).lower() for a in x]
    )

    teams_total = len(teams)

    st.caption(f"{teams_total} týmů")

    column_cnt = 4

    for i, (_, team) in enumerate(teams.iterrows()):
        if i % column_cnt == 0:
            cols = st.columns(column_cnt)

        subcol = cols[i % column_cnt]

        with subcol:
            team_name = f"<h5>{db.get_team_link(team)}</h5>"
            img_path = team["team_photo"] or "static/team.png"
            img = db.read_image(img_path, thumbnail="100_square")

            member1 = db.get_participant_by_id(team["member1"])
            members = [get_member_link(member1["id"], member1["name"])]

            if team["member2"]:
                member2 = db.get_participant_by_id(team["member2"])
                members.append(get_member_link(member2["id"], member2["name"]))

            if team["member3"]:
                member3 = db.get_participant_by_id(team["member3"])
                members.append(get_member_link(member3["id"], member3["name"]))

            members = ", ".join(members)
            st.image(img)

            st.markdown(f"{team_name}", unsafe_allow_html=True)
            st.markdown(
                f"<div style='margin-top: -15px; margin-bottom:0px;'>{members}</div>",
                unsafe_allow_html=True,
            )

            if team["team_motto"]:
                motto = utils.escape_html(team["team_motto"])
                motto = motto[:100] + "..." if len(motto) > 100 else motto

                st.markdown(
                    f"<div style='margin-top: -5px; margin-bottom:30px; font-size:12px; color: grey'>{motto}</div>",
                    unsafe_allow_html=True,
                )
            else:
                st.markdown("")


def main():
    params = st.query_params

    if params.get("team_id"):
        team_id = params["team_id"]

        show_profile(team_id)
        st.stop()

    st.markdown(f"# Týmy")

    st.markdown(
        """
    <style>
    [data-testid=stImage]{
            text-align: center;
            display: block;
            margin-left: auto;
            margin-right: auto;
        }
    [data-testid=stVerticalBlock]{
            text-align: center;
    }
    [data-baseweb=tab-list] {
        justify-content: center;
    }
    </style>
    """,
        unsafe_allow_html=True,
    )

    show_teams()


if __name__ == "__main__":
    main()
