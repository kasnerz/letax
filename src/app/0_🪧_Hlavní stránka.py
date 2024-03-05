#!/usr/bin/env python3

import streamlit as st
from database import get_database
import utils
import random
import pandas as pd

st.set_page_config(
    layout="wide",
    page_title=f"Letní X-Challenge",
    page_icon="static/favicon.png",
    # initial_sidebar_state="expanded",
)
params = st.query_params

event_id = utils.get_event_id(params)
db = get_database(event_id=event_id)
st.session_state["event"] = db.get_event()


def back_btn():
    # delete query params
    params = st.query_params
    page = params.get("page", 0)
    st.query_params.page = page


def load_posts(db, team_filter=None, challenge_filter=None, checkpoint_filter=None):
    posts = db.get_posts(team_filter, challenge_filter, checkpoint_filter)

    if not posts:
        st.write("### Čekáme na vaše příspěvky! 💙")
        st.stop()

    # sort by date
    posts.sort(key=lambda x: x["created"], reverse=True)

    return posts


def shorten(s, post_id, max_len=250):
    if len(s) > max_len:
        return (
            s[:max_len]
            + f"<b><a href='/Příspěvky?post={post_id}&event_id={event_id}' class='app-link' target='_self'> (...)</a></b>"
        )
    return s


def get_member_link(member_id, member_name):
    return f"<a href='/Účastníci?id={member_id}&event_id={event_id}' class='app-link' target='_self'>{member_name}</a>"


def show_overview():
    event = db.get_event()
    year = db.get_year()

    st.title(f"Letní X-Challenge {year}")
    posts = load_posts(db)

    post_gallery_cnt = min(3, len(posts))
    if event["status"] == "past":
        # select 3 random posts
        posts = random.sample(posts, post_gallery_cnt)
    elif event["status"] == "ongoing":
        # select 3 last posts (posts is a dataframe)
        posts = posts[:post_gallery_cnt]
    else:
        st.info("Akce ještě nezačala.")
        st.stop()

    st.markdown(
        """
        <style>
        div.stMarkdown > * > p {
            font-size: large !important;
        }
        .stVideo {
            max-height: 200px; /* Set the maximum height as a percentage of the viewport height */
            overflow: hidden; /* Hide any overflowing content */
        }
        .stVideo video {
            width: auto; /* Let the video adjust its width to maintain aspect ratio */
            height: 100%; /* Expand the video to fill the container's height */
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    if event["status"] == "past":
        st.caption(
            f"Letní X-Challenge {year} je za námi! Prohlédni si, jak akce probíhala."
        )
        st.divider()
        st.markdown(
            f"<h2><a href='/Příspěvky?event_id={event_id}' target='_self' class='app-link'>Příspěvky</a></h2>",
            unsafe_allow_html=True,
        )
    else:
        st.divider()
        st.markdown(
            f"<h2><a href='/Příspěvky?event_id={event_id}' target='_self' class='app-link'>Poslední příspěvky</a></h2>",
            unsafe_allow_html=True,
        )

    cols = st.columns(post_gallery_cnt, gap="large")

    for col, post in zip(cols, posts):
        action_name = post["action_name"]
        action_type = post["action_type"]

        team = db.get_team_by_id(post["team_id"])
        description = post["comment"]

        if action_type == "challenge":
            action = db.get_action(action_type, action_name)
            category = action.get("category")
            action_type_icon = action["category"][0] if category else "💪"

            if action_type_icon.isalpha():
                action_type_icon = "💪"
        elif action_type == "checkpoint":
            action_type_icon = "📍"
        else:
            action_type_icon = "✍️"

        post_id = post["post_id"]
        link = f"<div style='margin-bottom:-10px; display:inline-block;'><h4><a href='/Příspěvky?post={post_id}&event_id={event_id}' target='_self' class='app-link'>{action_type_icon} {action_name} – {team['team_name']}</a></div>"

        with col:
            st.markdown(link, unsafe_allow_html=True)
            post_datetime = utils.convert_to_local_timezone(post["created"])
            st.caption(f"*{post_datetime}*")
            files = post["files"]
            for f in files:
                if f["type"].startswith("image"):
                    st.image(db.read_image(f["path"], thumbnail="150_square"))
                    break
            else:
                for f in files:
                    if f["type"].startswith("video"):
                        video_file = db.read_video(f["path"])
                        st.video(video_file)
                        break
            st.markdown(
                shorten(utils.escape_html(description), post_id, max_len=150),
                unsafe_allow_html=True,
            )

    st.divider()
    st.markdown(
        f"<h2><a href='/Týmy?event_id={event_id}' target='_self' class='app-link'>Nejlepší týmy</a></h2>",
        unsafe_allow_html=True,
    )
    best_teams = db.get_teams_with_awards()

    if best_teams.empty:
        # find the teams with most points
        teams_overview = db.get_teams_overview()
        best_teams = (
            pd.DataFrame(teams_overview).sort_values("points", ascending=False).head(4)
        )

    best_teams = best_teams.to_dict("records")
    column_cnt = len(best_teams)
    cols = st.columns(column_cnt)

    # display best teams with their awards
    for col, team in zip(cols, best_teams):
        with col:
            if team.get("award"):
                category = team["award"]
                st.markdown(f"##### 🏆️ {category}")
            else:
                points = int(team["points"])
                st.markdown(f"##### ⭐️ {points} bodů")

            team_name = f"<h5>{db.get_team_link(team)}</h5>"

            img_path = team["team_photo"] or "static/team.png"
            img = db.read_image(img_path, thumbnail="100_square")

            member1 = db.get_participant_by_id(team["member1"])
            members = [get_member_link(member1["id"], member1["name"])]

            if team["member2"]:
                member2 = db.get_participant_by_id(team["member2"])
                members.append(get_member_link(member2["id"], member2["name"]))

            members = ", ".join(members)
            st.image(img)

            st.markdown(f"{team_name}", unsafe_allow_html=True)
            st.markdown(
                f"<div style='margin-top: -15px; margin-bottom: 25px;'>{members}</div>",
                unsafe_allow_html=True,
            )

    st.divider()
    st.markdown(
        f"<h2><a href='/Mapa_týmů?event_id={event_id}' target='_self' class='app-link'>Mapa týmů</a></h2>",
        unsafe_allow_html=True,
    )

    from map import show_positions, render_map

    m, _ = show_positions(db)
    render_map(m)


def main():
    utils.page_wrapper()

    show_overview()


if __name__ == "__main__":
    main()
