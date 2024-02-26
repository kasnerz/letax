#!/usr/bin/env python3

import streamlit as st
from database import get_database
import utils
import random


def back_btn():
    # delete query params
    params = st.experimental_get_query_params()

    if params.get("page"):
        page = params["page"][0]
    else:
        page = 0

    st.experimental_set_query_params(page=page)


def load_posts(team_filter=None, challenge_filter=None, checkpoint_filter=None):
    db = get_database()
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
            + f"<b><a href='/Příspěvky?post={post_id}' class='app-link' target='_self'> (...)</a></b>"
        )
    return s


def get_member_link(member_id, member_name):
    return f"<a href='/Účastníci?id={member_id}' class='app-link' target='_self'>{member_name}</a>"


def show_overview():
    db = get_database()
    year = db.get_settings_value("xchallenge_year")

    posts = load_posts()

    # select 5 random posts

    post_gallery_cnt = min(3, len(posts))
    posts = random.sample(posts, post_gallery_cnt)

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
    st.title(f"Letní X-Challenge {year}")
    st.caption("Letní X-Challenge 2023 je za námi! Prohlédni si, jak akce probíhala.")
    st.divider()
    st.markdown(
        f"<h2><a href='/Příspěvky' target='_self' class='app-link'>Příspěvky</a></h2>",
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
            action_type_icon = action["category"][0] if action.get("category") else "💪"
        elif action_type == "checkpoint":
            action_type_icon = "📍"
        else:
            action_type_icon = "✍️"

        post_id = post["post_id"]
        link = f"<div style='margin-bottom:-10px; display:inline-block;'><h4><a href='/Příspěvky?post={post_id}' target='_self' class='app-link'>{action_type_icon} {action_name} – {team['team_name']}</a></div>"

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
        f"<h2><a href='/Týmy' target='_self' class='app-link'>Nejlepší týmy</a></h2>",
        unsafe_allow_html=True,
    )
    teams = db.get_teams()

    best_teams = {
        "Máslo v Akci!": "🏆️ Body",
        "888": "🏆️ Checkpoint",
        "DivoZeny": "🏆️ Challenge",
        "Banánový dezert": "🏆️ Reporty",
        "Sandálky": "🏆️ Sebepřekonání",
    }
    # find the best teams by team_name
    teams = [teams[teams["team_name"] == team_name].iloc[0] for team_name in best_teams]

    column_cnt = len(best_teams)
    cols = st.columns(column_cnt)

    # display best teams witdh their awards
    for col, team in zip(cols, teams):
        with col:
            category = best_teams[team["team_name"]]
            st.markdown(f"##### {category}")
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
        f"<h2><a href='/Mapa_týmů' target='_self' class='app-link'>Mapa týmů</a></h2>",
        unsafe_allow_html=True,
    )

    from map import show_positions, render_map

    m, _ = show_positions()
    render_map(m)


def main():
    st.set_page_config(
        layout="wide",
        page_title=f"Letní X-Challenge",
        page_icon="static/favicon.png",
        # initial_sidebar_state="expanded",
    )

    utils.page_wrapper()

    params = st.experimental_get_query_params()
    show_overview()


if __name__ == "__main__":
    main()
