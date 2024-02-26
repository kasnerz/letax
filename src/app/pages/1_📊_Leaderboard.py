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
    page_title="Leaderboard", page_icon="static/favicon.png", layout="wide"
)
utils.page_wrapper()

db = get_database()


def main():
    st.title("Leaderboard")
    teams_overview = db.get_teams_overview()

    # teams_overview[i] contains a key "posts" with a df containing all the posts for the team
    # compute how many occurences of each action type (challenge, checkpoint, ...) there were according to "action_type" column
    for i, team in enumerate(teams_overview):
        posts = team["posts"]
        posts["action_type"].value_counts()
        for action_type in ["challenge", "checkpoint", "story"]:
            teams_overview[i][action_type] = (
                posts["action_type"].value_counts().get(action_type, 0)
            )

    table = pd.DataFrame(
        teams_overview,
        columns=[
            "team_name",
            "points",
            "member1_name",
            "member2_name",
            "challenge",
            "checkpoint",
            "story",
        ],
    )

    table = table.sort_values(by="points", ascending=False)
    table = table.reset_index(drop=True)
    table.index += 1
    table.index.name = "Pořadí"

    table = table.rename(
        columns={
            "team_name": "Tým",
            "member1_name": "Člen 1",
            "member2_name": "Člen 2",
            "points": "Body",
            "challenge": "Výzvy",
            "checkpoint": "Checkpointy",
            "story": "Příspěvky",
        }
    )

    st.dataframe(
        table,
        column_config={
            "Body": st.column_config.NumberColumn(
                format="%d ⭐️",
            )
        },
        use_container_width=True,
        height=600,
    )


if __name__ == "__main__":
    main()
