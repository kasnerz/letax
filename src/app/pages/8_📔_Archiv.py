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
st.session_state["active_event"] = db.get_active_event()
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
        # events = [event for event in events if event["stat"] is True]

        if not events:
            st.info("Zatím nebyly nalezeny žádné ročníky.")
            st.stop()

        active_event = st.session_state.event
        # keep year and event_id so that we can use event_id later
        selected_event = st.selectbox(
            "Vyber ročník",
            events,
            format_func=lambda x: x["year"],
            index=events.index(active_event) if active_event else 0,
        )

        change_event = st.button("Změnit ročník")

        if selected_event["year"] == "2022":
            st.warning(
                "Upozornění: ročník 2022 byl do appky přenesený z původního webu a příspěvky ani body nemusí být kompletní."
            )

        if change_event:
            st.session_state.event = selected_event

            st.success("Změna ročníku byla úspěšná.")
            time.sleep(2)
            utils.clear_cache()
            st.rerun()

    with columns[1]:
        st.image("static/logo.png", width=200)


if __name__ == "__main__":
    main()
