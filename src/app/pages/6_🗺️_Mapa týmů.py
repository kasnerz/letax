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
from folium.plugins import BeautifyIcon
from streamlit_folium import folium_static

st.set_page_config(page_title="Mapa týmů", page_icon="static/favicon.png", layout="wide")
utils.style_sidebar()
db = get_database()

make_map_responsive = """
     <style>
     [title~="st.iframe"] { width: 100%}
     </style>
    """
st.markdown(make_map_responsive, unsafe_allow_html=True)


def show_map():
    last_locations = db.get_last_locations()

    if last_locations is None:
        st.info("Žádný tým nezaznamenal svoji polohu")
        st.stop()

    # center on Liberty Bell, add marker
    m = folium.Map(
        location=[last_locations.latitude.mean(), last_locations.longitude.mean()],
        zoom_start=4,
        # tiles="Stamen Terrain",
        # tiles="cartodbpositron",
        # tiles="https://mapserver.mapy.cz/turist-m/{z}-{x}-{y}.png",
        attr="<a href=https:/stamen.com/>Stamen.com</a>",
    )
    # folium.TileLayer("").add_to(m)

    for _, location in last_locations.iterrows():
        team = db.get_team_by_id(location["team_id"])
        team_icon = team["location_icon"] or "user"
        team_color = team["location_color"] or "red"
        team_icon_color = team["location_icon_color"] or "white"

        team_name = team["team_name"]
        if not db.is_team_visible(team):
            continue

        date = location["date"]
        ago_str = utils.ago(date)
        # ago_str = date

        text = "<b>" + team_name + "</b>"

        if location["comment"]:
            popup = f"{location['comment']}<br><br>"
        else:
            popup = ""

        popup += f"<i>{ago_str}</i>"

        folium.Marker(
            [location["latitude"], location["longitude"]],
            popup=popup,
            tooltip=text,
            icon=folium.Icon(color=team_color, icon=team_icon, icon_color=team_icon_color, prefix="fa"),
        ).add_to(m)

    checkpoints = db.get_table_as_df("checkpoints")

    for _, checkpoint in checkpoints.iterrows():
        icon_dot = BeautifyIcon(
            # background_color="darkblue",
            # icon="arrow-down",
            # icon_shape="marker",
            # text_color="white",
            icon_shape="circle-dot",
            border_color="grey",
            border_width=3,
        )
        folium.Marker(
            [checkpoint["latitude"], checkpoint["longitude"]], tooltip=checkpoint["name"], icon=icon_dot
        ).add_to(m)

    # call to render Folium map in Streamlit
    folium_static(m, width=None, height=500)

    # # show the locations on the map
    # st.map(last_locations)


def main():
    st.title("Mapa týmů")
    st.caption(
        "Na mapě je zobrazena poslední poloha týmů, které svou polohu zaznamenaly. Historii konkrétního týmu najdeš na jejich stránce."
    )
    show_map()


if __name__ == "__main__":
    main()
