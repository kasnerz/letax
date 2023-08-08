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

st.set_page_config(page_title="Mapa", page_icon="static/favicon.png", layout="wide")
utils.style_sidebar()
db = get_database()


def show_map():
    # get last locations of all teams
    teams = db.get_table_as_df("teams")
    last_locations = []

    for _, team in teams.iterrows():
        # get last location of the team
        last_location = db.get_last_location(team)

        if last_location is None:
            continue

        last_locations.append(last_location)

    if not last_locations:
        st.info("Žádný tým nezaznamenal svoji polohu")
        st.stop()

    # create dataframe from the list of locations
    last_locations = pd.DataFrame(last_locations)

    # center on Liberty Bell, add marker
    m = folium.Map(
        location=[last_locations.latitude.mean(), last_locations.longitude.mean()],
        zoom_start=5,
        # tiles="Stamen Terrain",
        # tiles="cartodbpositron",
        # tiles="https://mapserver.mapy.cz/turist-m/{z}-{x}-{y}.png",
        attr="<a href=https:/stamen.com/>Stamen.com</a>",
    )
    # folium.TileLayer("").add_to(m)

    for _, location in last_locations.iterrows():
        team = db.get_team_by_id(location["team_id"])

        team_name = team["team_name"]
        if not db.is_team_visible(team):
            continue

        text = "<b>" + team_name + "</b><br>" + location["comment"]
        popup = f"<b>{team_name}</b><br><i> {location['date']}</i>"

        folium.Marker(
            [location["latitude"], location["longitude"]],
            popup=popup,
            tooltip=text,
            icon=folium.Icon(color="red", icon="user"),
        ).add_to(m)

    # call to render Folium map in Streamlit
    st_data = st_folium(m, width=900)

    # # show the locations on the map
    # st.map(last_locations)

    st.info("Na mapě jsou zobrazeny pouze týmy, které zaznamenaly svoji polohu a povolily její veřejné sdílení")


def main():
    st.title("Mapa týmů")
    show_map()


if __name__ == "__main__":
    main()
