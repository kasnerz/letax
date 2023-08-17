#!/usr/bin/env python3

import streamlit as st
from database import get_database
import utils

CACHE_TTL = 60 * 60 * 24


def text_bubble(text, color):
    return f'<p style="background-color:{color}; padding:5px; border-radius:5px; display:inline-block;">{text}</p>'


def back_btn():
    # delete query params
    params = st.experimental_get_query_params()

    if params.get("page"):
        page = params["page"][0]
    else:
        page = 0

    st.experimental_set_query_params(page=page)


def prev_page(page):
    st.experimental_set_query_params(page=page - 1)


def next_page(page):
    st.experimental_set_query_params(page=page + 1)


def set_page():
    # get value of the slider `page_slider`
    page = st.session_state.page_slider
    st.experimental_set_query_params(page=page)


def show_post(post_id):
    st.markdown(
        """
        <style>
        div.stMarkdown > * > p {
            font-size: large !important;
        }
        .stVideo {
            max-height: 80vh; /* Set the maximum height as a percentage of the viewport height */
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

    st.button("Zpět", on_click=back_btn)

    db = get_database()
    post = db.get_post_by_id(post_id)

    if not post:
        st.error("Příspěvek nebyl nalezen.")
        st.stop()

    team = db.get_team_by_id(post["team_id"])
    action = post["action_name"]
    description = post["comment"]
    files = post["files"]

    link_color = db.get_settings_value("link_color")

    st.markdown(
        f"## {action}",
    )
    st.markdown(
        f"<h4>{db.get_team_link(team)}</h4>",
        unsafe_allow_html=True,
    )

    post_datetime = utils.convert_to_local_timezone(post["created"])
    st.caption(f"*{post_datetime}*")

    if description:
        # escape html
        description = utils.escape_html(description)
        st.markdown(description, unsafe_allow_html=True)
        st.divider()

    images = [db.read_image(f["path"], thumbnail="1000") for f in files if f["type"].startswith("image")]

    if images:
        cols = st.columns(min(3, len(images)))
        for i, image in enumerate(images):
            col = cols[i % 3]
            col.image(image, use_column_width=True)

    videos = [f["path"] for f in files if f["type"].startswith("video")]
    if videos:
        for video in videos:
            video_file = db.read_video(video)
            st.video(video_file)


def load_posts(team_filter=None, challenge_filter=None, checkpoint_filter=None):
    db = get_database()
    posts = db.get_posts(team_filter, challenge_filter, checkpoint_filter)

    if not posts:
        st.write("### Čekáme na vaše příspěvky! 💙")
        st.stop()

    # sort by date
    posts.sort(key=lambda x: x["created"], reverse=True)

    return posts


def shorten(s, post_id, page, link_color, max_len=250):
    if len(s) > max_len:
        return (
            s[:max_len]
            + f"<b><a href='/?post={post_id}&page={page}' target='_self' style='text-decoration: none; color: {link_color};'> (...)</a></b>"
        )
    return s


def show_overview(page):
    db = get_database()
    year = db.get_settings_value("xchallenge_year")

    team_options = [""] + sorted(list(db.get_teams()["team_name"]), key=str.lower)
    challenge_options = [""] + sorted(list(db.get_table_as_df("challenges")["name"]), key=str.lower)

    checkpoint_options = [""] + sorted(list(db.get_table_as_df("checkpoints")["name"]), key=str.lower)

    # include css
    st.markdown(
        """
        <style>
        div[data-testid="stExpander"] div[role="button"] {
            padding-top: 3px !important;
            padding-bottom: 3px !important;
        }
        """,
        unsafe_allow_html=True,
    )
    st.sidebar.caption("Filtrovat feed")
    # st.sidebar.markdown("**Filtrovat**")
    team_filter = st.sidebar.selectbox("Tým:", options=team_options, key="team_filter_selector")
    challenge_filter = st.sidebar.selectbox("Výzvy:", options=challenge_options, key="challenge_filter_selector")

    checkpoint_filter = st.sidebar.selectbox(
        "Checkpointy:", options=checkpoint_options, key="checkpoint_filter_selector"
    )

    st.title(f"Letní X-Challenge {year}")
    cols = st.columns([1, 3, 1])

    posts = load_posts(team_filter=team_filter, challenge_filter=challenge_filter, checkpoint_filter=checkpoint_filter)

    col_layout = [5, 2]
    cols = st.columns(col_layout)

    page_size = int(db.get_settings_value("feed_page_size"))
    page_count = len(posts) // page_size + 1
    page = min(page, page_count - 1)

    posts = posts[page * page_size : (page + 1) * page_size]

    for post in posts:
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
        team_link = db.get_team_link(team)

        link_color = db.get_settings_value("link_color")
        link = f"<div style='margin-bottom:-10px; display:inline-block;'><h4><a href='/?post={post_id}&page={page}' target='_self' style='text-decoration: none; color: {link_color};'>{action_type_icon} {action_name} – {team['team_name']}</a></div>"
        # link = f"<div style='margin-bottom:-10px; display:inline-block;'><h4><a href='/?post={post_id}&page={page}' target='_self' style='text-decoration: none; color: {link_color};'>{action_type_icon} {action_name}</a> – {team_link}</div>"

        st.markdown(link, unsafe_allow_html=True)
        cols = st.columns(col_layout)
        with cols[0]:
            post_datetime = utils.convert_to_local_timezone(post["created"])
            st.caption(f"*{post_datetime}*")
            st.markdown(
                shorten(utils.escape_html(description), post_id, page, link_color),
                unsafe_allow_html=True,
            )
        with cols[1]:
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

        st.divider()

    cols = st.columns([1, 3, 1])

    with cols[1]:
        st.number_input(
            f"Stránka {page}/{page_count-1}",
            min_value=0,
            max_value=page_count - 1,
            value=page,
            key="page_slider",
            on_change=set_page,
        )
    # cols[1].slider(
    #     "Stránka",
    #     min_value=0,
    #     max_value=page_count - 1,
    #     value=page,
    #     label_visibility="hidden",
    #     on_change=set_page,
    #     key="page_slider",
    # )
    # if page > 0:
    #     cols[0].button("Přechozí", args=(page,), on_click=prev_page)
    # if page < page_count - 1:
    #     cols[4].button("Další", args=(page,), on_click=next_page)


def main():
    st.set_page_config(
        layout="centered",
        page_title=f"Letní X-Challenge",
        page_icon="static/favicon.png",
        # initial_sidebar_state="expanded",
    )

    utils.style_sidebar()
    params = st.experimental_get_query_params()

    if params.get("post"):
        post = params["post"][0]
        show_post(post)
    else:
        if params.get("page"):
            page = params["page"][0]
        else:
            page = 0
        show_overview(int(page))


if __name__ == "__main__":
    main()
