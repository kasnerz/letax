#!/usr/bin/env python3

import streamlit as st
import streamlit_authenticator as stauth
import os
import time
import yaml
import utils
from yaml.loader import SafeLoader
import time
import pandas as pd
from database import get_database


st.set_page_config(
    page_title="Archiv", page_icon="static/favicon.png", layout="centered"
)
params = st.query_params
event_id = utils.get_event_id(params)
db = get_database(event_id=event_id)
st.session_state["event"] = db.get_event()
utils.page_wrapper()


def main():
    st.title("Archiv")

    columns = st.columns([2, 1], gap="large")

    with columns[0]:
        st.markdown(
            """
            Zde můžeš přepínat mezi jednotlivými ročníky X-Challenge.
            """
        )
        # dropdown
        events = db.get_events()
        events = [event for event in events if event["status"] != "draft"]

        if not events:
            st.info("Zatím nebyly nalezeny žádné ročníky.")
            st.stop()

        active_event = st.session_state.get("event", None)
        active_event_idx = [
            i for i, event in enumerate(events) if event["id"] == active_event
        ]
        # keep year and event_id so that we can use event_id later
        selected_event = st.selectbox(
            "Vyber ročník",
            events,
            format_func=lambda x: x["year"],
            index=active_event_idx[0] if active_event_idx else 0,
        )

        # columns_btn = st.columns([1, 1, 1])

        # with columns_btn[0]:
        change_event = st.button("Změnit ročník")
        # with columns_btn[1]:
        # back_to_active = st.button("Zpět na aktuální ročník")

        if selected_event["year"] == 2022:
            st.warning(
                "Upozornění: ročník 2022 byl do appky portovaný z webu a příspěvky ani body nemusí být kompletní."
            )

        if change_event:
            st.session_state.event = selected_event
            st.cache_data.clear()
            st.rerun()

        # if back_to_active:
        #     st.session_state.event = None
        #     st.rerun()

    with columns[1]:
        st.image("static/logo.png", width=200)


if __name__ == "__main__":
    main()
