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

params = st.query_params
event_id = utils.get_event_id(params)
db = get_database(event_id=event_id)
st.session_state["event"] = db.get_event()
utils.page_wrapper()


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
            "team_id",
            "member1_name",
            "member2_name",
            "challenge",
            "checkpoint",
            "story",
            "spent",
        ],
    )

    table = table.sort_values(by="points", ascending=False)
    table = table.reset_index(drop=True)
    table.index += 1
    table.index.name = "Pořadí"

    # replace the values in `team_id` with "Týmy?team_id={team_id}"
    table["team_id"] = table["team_id"].apply(
        lambda x: f"/Týmy?team_id={x}&event_id={event_id}" if x else ""
    )

    table = table.rename(
        columns={
            "team_name": "Tým",
            "member1_name": "Člen 1",
            "member2_name": "Člen 2",
            "team_id": "Stránka",
            "points": "Body",
            "challenge": "Výzvy",
            "checkpoint": "Checkpointy",
            "story": "Příspěvky",
            "spent": "Utraceno (Kč)",
        }
    )

    st.dataframe(
        table,
        column_config={
            "Body": st.column_config.NumberColumn(
                format="%d",
            ),
            "Stránka": st.column_config.LinkColumn(display_text="🔗", width="small"),
            "Utraceno (Kč)": st.column_config.NumberColumn(
                format="%d",
            ),
        },
        use_container_width=True,
        height=600,
    )


if __name__ == "__main__":
    main()
