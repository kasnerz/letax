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
from unidecode import unidecode
import folium
from streamlit_folium import st_folium

st.set_page_config(page_title="Týmy", page_icon="static/favicon.png", layout="wide")
utils.style_sidebar()
db = get_database()


def backbtn():
    st.experimental_set_query_params()


def show_profile(team_id):
    st.button("Zpět", on_click=backbtn)

    team = db.get_team_by_id(team_id)
    if not team:
        st.error("Tým nebyl nalezen.")
        st.stop()

    columns = st.columns([1, 3, 2])

    with columns[1]:
        st.write(f"## {team['team_name']}")

        member_1 = db.get_participant_by_id(team["member1"])
        member_string = f"{member_1['name']}"

        if team["member2"]:
            member_2 = db.get_participant_by_id(team["member2"])
            member_string += f" & {member_2['name']}"

        st.write(f"##### {member_string}")

        if team["team_motto"]:
            st.write(f"{team['team_motto']}")

        if team["team_web"]:
            st.markdown(f"🔗 [{team['team_web']}]({team['team_web']})")

    with columns[2]:
        photo_path = team["team_photo"]
        if photo_path:
            st.image(db.read_image(photo_path))
        else:
            st.image("static/team.png")


def get_team_name_view(team):
    link_color = db.get_settings_value("link_color")
    name = team["team_name"]
    team_id = team["team_id"]

    link = f"<div><a href='/Týmy?id={team_id}'  target='_self' style='text-decoration: none;'><h5 style='color: {link_color};'>{name}</h5></a></div>"

    return link


@st.cache_data(show_spinner=False)
def show_teams():
    teams = db.get_teams()

    if teams.empty:
        st.info("Zatím nemáme žádné týmy. Přihlas se a založ si svůj!")
        st.stop()

    # considering unicode characters in Czech alphabet
    teams = teams.sort_values(by="team_name", key=lambda x: [unidecode(a) for a in x])

    column_cnt = 4

    for i, (_, team) in enumerate(teams.iterrows()):
        if i % column_cnt == 0:
            cols = st.columns(column_cnt)

        subcol = cols[i % column_cnt]

        with subcol:
            team_name = get_team_name_view(team)
            img_path = team["team_photo"] or "static/team.png"
            img = utils.resize_image(db.read_image(img_path), crop_ratio="1:1")

            member1 = db.get_participant_by_id(team["member1"]).get("name")
            members = member1

            if team["member2"]:
                member2 = db.get_participant_by_id(team["member2"])
                members += f", {member2['name']}"

            st.image(img, width=60)

            st.markdown(f"{team_name}", unsafe_allow_html=True)
            st.markdown(f"<div style='margin-top: -15px; margin-bottom:0px;'>{members}</div>", unsafe_allow_html=True)

            if team["team_motto"]:
                st.caption(team["team_motto"])
            else:
                st.markdown("")


def main():
    params = st.experimental_get_query_params()
    xchallenge_year = db.get_settings_value("xchallenge_year")

    if params.get("id"):
        team_id = params["id"][0]

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
