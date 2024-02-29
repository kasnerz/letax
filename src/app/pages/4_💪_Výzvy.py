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


def display_challenge(challenge):
    points = challenge["points"]

    if not points:
        points = "0"

    # if points can be rounded to int without loss of precision, do it
    if points == int(points):
        points = int(points)

    st.markdown("#### " + challenge["name"] + " (" + str(points) + ")")
    st.markdown(f"{challenge['description']}")
    st.divider()


def main():
    st.title("Výzvy")

    challenges = db.get_table_as_df("challenges")

    if challenges.empty:
        st.info("Na tento ročník zatím výzvy nejsou. Ale budou!")
        st.stop()

    # sort by name: letter case insensitive, interpunction before numbers
    challenges = utils.sort_challenges(challenges)
    categories = list(challenges.category.unique())
    tab_list = ["💪 vše"] + categories
    tabs = st.tabs(tab_list)

    for _, challenge in challenges.iterrows():
        with tabs[0]:
            display_challenge(challenge)

        if challenge["category"] in categories:
            with tabs[categories.index(challenge["category"]) + 1]:
                display_challenge(challenge)

        else:
            utils.log(
                f'Category {challenge["category"]} does not have its own tab',
                level="warning",
            )


if __name__ == "__main__":
    user, team = login_page()

    if user:
        cols = st.columns([1, 3, 1])
        with cols[1]:
            main()
