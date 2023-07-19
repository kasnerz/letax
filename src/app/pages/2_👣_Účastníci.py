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

st.set_page_config(page_title="Účastníci", page_icon="static/favicon.png", layout="wide")
utils.style_sidebar()
db = get_database()


def backbtn():
    st.experimental_set_query_params()


def show_profile(pax_id):
    st.button("Zpět", on_click=backbtn)

    pax = db.get_participant_by_id(pax_id)
    team = db.get_team_for_user(pax_id)

    if not pax:
        st.error("Účastník nebyl nalezen.")
        st.stop()

    columns = st.columns([1, 3, 2])

    with columns[1]:
        st.write(f"## {pax['name']}")
        st.write(f"##### {team['team_name']}")

        if pax["bio"]:
            st.write(f"{pax['bio']}")

    with columns[2]:
        photo_path = pax["photo"]
        if photo_path:
            st.image(db.read_image(photo_path))
        else:
            st.image("static/avatar.png")


def get_profile_photo(pax):
    # check if pax["registered"] is nan
    is_registered = pax.get("registered") and not pd.isna(pax["registered"])

    if is_registered:
        # check if the user has a profile picture
        if pax["photo"]:
            avatar = pax["photo"]
        else:
            avatar = "static/avatar.png"
    else:
        avatar = "static/avatar_inactive.png"

    return avatar


def get_participant_name_view(pax):
    is_registered = pax.get("registered") and not pd.isna(pax["registered"])

    link_color = db.get_settings_value("link_color")
    name = pax["name"] or pax["name_web"]

    if is_registered:
        pax_id = pax["id"]
        link = f"<div><a href='/Účastníci?id={pax_id}'  target='_self' style='text-decoration: none;'><h5 style='color: {link_color};'>{name}</h5></a></div>"
    else:
        link = f"<div><h5>{name}</h5></div>"

    return link


@st.cache_data
def get_participants_view():
    # timeit
    participants = db.get_participants(include_non_registered=True, fetch_teams=True)

    if participants.empty:
        return None

    # add column profile_photo_view to the dataframe
    participants["profile_photo_view"] = participants.apply(get_profile_photo, axis=1)
    participants["name_view"] = participants.apply(lambda x: get_participant_name_view(x), axis=1)

    return participants


def show_participants():
    participants = get_participants_view()
    if participants is None:
        st.info("Nikdo se zatím nezaregistroval. Přidáš se ty?")
        st.stop()

    column_cnt = 5
    img_cache = {}

    for i, (_, pax) in enumerate(participants.iterrows()):
        if i % column_cnt == 0:
            cols = st.columns(column_cnt)

        subcol = cols[i % column_cnt]

        with subcol:
            name = pax["name_view"]
            team_name = pax["team_name"]

            if img_cache.get(pax["profile_photo_view"]):
                img = img_cache[pax["profile_photo_view"]]
            else:
                img = utils.resize_image(db.read_image(pax["profile_photo_view"]), crop_ratio="1:1", circle=True)
                img_cache[pax["profile_photo_view"]] = img

            st.image(img, width=60)
            st.markdown(f"{name}", unsafe_allow_html=True)

            if team_name:
                st.markdown(
                    f"<div style='margin-top: -15px; margin-bottom:20px;'>{team_name}</div>", unsafe_allow_html=True
                )
            else:
                st.markdown("")


def main():
    params = st.experimental_get_query_params()
    xchallenge_year = db.get_settings_value("xchallenge_year")

    if params.get("id"):
        pax_id = params["id"][0]

        show_profile(pax_id)
        st.stop()

    st.markdown(f"# Účastníci {xchallenge_year}")

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
    show_participants()


if __name__ == "__main__":
    main()
