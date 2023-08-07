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

st.set_page_config(page_title="Checkpointy", page_icon="static/favicon.png", layout="centered")
utils.style_sidebar()
db = get_database()


def main():
    st.title("Checkpointy")

    gmaps_url = db.get_settings_value("map_embed_url")

    # create link to google maps
    st.markdown(f"""
    <iframe
        width="100%"
        height="480"
        frameborder="0" style="border:0"
        src="{gmaps_url}"
        allowfullscreen>
    </iframe>
    """, unsafe_allow_html=True)



    checkpoints = db.get_table_as_df("checkpoints")

    if checkpoints.empty:
        st.info("Na tento ročník zatím checkpointy nejsou. Ale budou!")
        st.stop()

    embed_url = db.get_settings_value("map_embed_url")
    link_color = db.get_settings_value("link_color")
    # st.components.v1.iframe(embed_url, height=480, scrolling=True)

    # sort by name
    checkpoints = checkpoints.sort_values(by="name", key=lambda x: [unidecode(a) for a in x])

    for _, checkpoint in checkpoints.iterrows():
        gmaps_url = f"http://www.google.com/maps/place/{checkpoint['latitude']},{checkpoint['longitude']}"
        link = f"<div style='margin-bottom:-10px; display:inline-block;'><a href='{gmaps_url}' style='text-decoration: none;'><h4 style='color: {link_color};'>{checkpoint['name']} ({checkpoint['points']})</b></h4></a></div>"

        st.markdown(link, unsafe_allow_html=True)
        # st.caption(f", ")
        st.markdown(f"{checkpoint['description']}")
        # st.markdown("##### Výzva")
        st.markdown(f"**Výzva:** *{checkpoint['challenge']}*")
        st.divider()


if __name__ == "__main__":
    main()
