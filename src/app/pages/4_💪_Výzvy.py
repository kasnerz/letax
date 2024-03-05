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

st.set_page_config(page_title="Výzvy", page_icon="static/favicon.png", layout="wide")

params = st.query_params
event_id = utils.get_event_id(params)
db = get_database(event_id=event_id)
st.session_state["event"] = db.get_event()
utils.page_wrapper()

from authenticator import login_page


def main(user):
    st.title("Výzvy")

    challenges = db.get_table_as_df("challenges")

    if challenges.empty:
        st.info("Na tento ročník zatím výzvy nejsou. Ale budou!")
        st.stop()

    tabs = st.tabs(["Seznam", "Popis"])

    available_actions = [x["id"] for x in db.get_available_actions(user, "challenge")]

    # sort by name: letter case insensitive, interpunction before numbers
    challenges = utils.sort_challenges(challenges)

    # if points can be rounded to int without loss of precision, do it
    challenges["points"] = challenges["points"].apply(
        lambda x: str(int(x)) if float(x) == int(x) else str(x)
    )

    # replace NaN with 0
    challenges["points"] = challenges["points"].fillna(0)

    challenges["Splněno"] = challenges.apply(
        lambda x: "✔️" if x["id"] not in available_actions else "-", axis=1
    )

    with tabs[0]:
        challenges_table = challenges.rename(
            columns={"name": "Název", "points": "Body", "category": "Kategorie"}
        )
        challenges_table = challenges_table[["Kategorie", "Název", "Body", "Splněno"]]
        challenges_table = challenges_table.reset_index(drop=True)
        st.write(
            challenges_table.to_html(
                escape=False, index=False, classes="table-display"
            ),
            unsafe_allow_html=True,
        )

    with tabs[1]:
        for _, challenge in challenges.iterrows():
            points = challenge["points"]

            st.markdown("#### " + challenge["name"] + " (" + str(points) + ")")
            st.markdown(f"{challenge['description']}")
            st.divider()


if __name__ == "__main__":
    user, team = login_page()

    if user:
        cols = st.columns([1, 3, 1])
        with cols[1]:
            main(user)
