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

st.set_page_config(
    page_title="Checkpointy", page_icon="static/favicon.png", layout="wide"
)
utils.page_wrapper()

from authenticator import login_page

event_id = st.session_state.event.get("id") if st.session_state.get("event") else None
db = get_database(event_id=event_id)


def main():
    st.title("Checkpointy")

    gmaps_url = db.get_gmaps_url(event_id)

    with st.expander("🗺️ Google mapy"):
        st.markdown(
            f"""
        <iframe
            width="100%"
            height="480"
            frameborder="0" style="border:0"
            src="{gmaps_url}"
            allowfullscreen>
        </iframe>
        """,
            unsafe_allow_html=True,
        )

    checkpoints = db.get_table_as_df("checkpoints")

    if checkpoints.empty:
        st.info("Na tento ročník zatím checkpointy nejsou. Ale budou!")
        st.stop()

    # sort by name
    checkpoints = checkpoints.sort_values(
        by="name", key=lambda x: [unidecode(a) for a in x]
    )

    for _, checkpoint in checkpoints.iterrows():
        gmaps_url = f"http://www.google.com/maps/place/{checkpoint['latitude']},{checkpoint['longitude']}"
        link = f"<div style='margin-bottom:-10px; display:inline-block;'><a href='{gmaps_url}' style='text-decoration: none;'><h4 class='app-link'>{checkpoint['name']} ({checkpoint['points']})</b></h4></a></div>"

        st.markdown(link, unsafe_allow_html=True)
        # st.caption(f", ")
        st.markdown(f"{checkpoint['description']}")
        # st.markdown("##### Výzva")
        st.markdown(f"**Výzva:** *{checkpoint['challenge']}*")
        st.divider()


if __name__ == "__main__":
    user, team = login_page()

    if user:
        cols = st.columns([1, 3, 1])
        with cols[1]:
            main()
