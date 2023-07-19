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

st.set_page_config(page_title="Výzvy", page_icon="static/favicon.png", layout="centered")
utils.style_sidebar()
db = get_database()


def display_challenge(challenge):
    st.markdown("#### " + challenge["name"] + " (" + str(challenge["points"]) + ")")
    st.markdown(f"{challenge['description']}")
    st.divider()


def main():
    st.title("Výzvy")

    challenges = db.get_table_as_df("challenges")

    if challenges.empty:
        st.info("Na tento ročník zatím výzvy nejsou. Ale budou!")
        st.stop()

    # sort by name
    challenges = challenges.sort_values(by="name")

    categories = db.get_settings_value("challenge_categories").split(",")
    tab_list = ["💪 vše"] + categories
    tabs = st.tabs(tab_list)

    for _, challenge in challenges.iterrows():
        with tabs[0]:
            display_challenge(challenge)

        if challenge["category"] in categories:
            with tabs[categories.index(challenge["category"]) + 1]:
                display_challenge(challenge)

        else:
            print(f'Kategorie {challenge["category"]} zatím nemá svůj tab')


if __name__ == "__main__":
    main()
