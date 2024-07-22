#!/usr/bin/env python3

import streamlit as st
from database import get_database
import utils
import folium
import datetime
from folium.plugins import BeautifyIcon
from streamlit_folium import folium_static

st.set_page_config(
    page_title="Mapa týmů", page_icon="static/favicon.png", layout="wide"
)

params = st.query_params
event_id = utils.get_event_id(params)
db = get_database(event_id=event_id)
st.session_state["event"] = db.get_event()
st.session_state["active_event"] = db.get_active_event()
utils.page_wrapper()

from map import show_last_shared_locations, show_positions, show_checkpoints, render_map

make_map_responsive = """
     <style>
     [title~="st.iframe"] { width: 100%}
     </style>
    """
st.markdown(make_map_responsive, unsafe_allow_html=True)


def main():
    st.title("Mapa týmů")
    cols = st.columns([2, 1], gap="large")

    with cols[0]:
        # st.caption(
        #     "Na mapě je zobrazena poslední poloha týmů, které svou polohu zaznamenaly. Historii konkrétního týmu najdeš na jejich stránce."
        # )
        m, last_locations = show_positions(db)
        show_checkpoints(db, m)
        render_map(m)

    with cols[1]:
        show_last_shared_locations(db, last_locations)


if __name__ == "__main__":
    main()
