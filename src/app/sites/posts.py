#!/usr/bin/env python3

import streamlit as st
from database import get_database
import utils

CACHE_TTL = 60 * 60 * 24
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
st.session_state["active_event"] = db.get_active_event()
utils.page_wrapper()


def text_bubble(text, color):
    return f'<p style="background-color:{color}; padding:5px; border-radius:5px; display:inline-block;">{text}</p>'


def back_btn():
    # delete query params
    params = st.query_params
    page = params.get("page", 0)
    st.query_params["page"] = page
    st.query_params["event_id"] = event_id
    del st.query_params["post"]


def prev_page(page):
    st.query_params.page = page - 1


def next_page(page):
    st.query_params.page = page + 1


def set_page():
    # get value of the slider `page_slider`
    page = st.session_state.page_slider
    st.query_params.page = page - 1


def show_post(db, post_id):
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

    st.button("← Příspěvky", on_click=back_btn)

    post = db.get_post_by_id(post_id)

    if not post:
        st.error("Příspěvek nebyl nalezen.")
        st.stop()

    team = db.get_team_by_id(post["team_id"])
    action = post["action_name"]
    description = post["comment"]
    files = post["files"]

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

    images = [
        db.read_image(f["path"], thumbnail="1000")
        for f in files
        if f["type"].startswith("image")
    ]

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


def load_posts(db, team_filter=None, challenge_filter=None, checkpoint_filter=None):
    posts = db.get_posts(team_filter, challenge_filter, checkpoint_filter)

    if not posts:
        st.write("### Čekáme na vaše příspěvky! 💙")
        st.stop()

    # sort by date
    posts.sort(key=lambda x: x["created"], reverse=True)

    return posts


def shorten(s, post_id, page, max_len=250):
    if len(s) > max_len:
        return (
            s[:max_len]
            + f"<b><a href='posts?post={post_id}&event_id={event_id}&page={page}' target='_self' class='app-link'> (...)</a></b>"
        )
    return s


def show_overview(db, page):
    team_options = [""] + sorted(list(db.get_teams()["team_name"]), key=str.lower)
    challenge_options = [""] + sorted(
        list(db.get_table_as_df("challenges")["name"]), key=str.lower
    )

    checkpoint_options = [""] + sorted(
        list(db.get_table_as_df("checkpoints")["name"]), key=str.lower
    )

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
    team_filter = st.sidebar.selectbox(
        "Tým:", options=team_options, key="team_filter_selector"
    )
    challenge_filter = st.sidebar.selectbox(
        "Výzvy:", options=challenge_options, key="challenge_filter_selector"
    )

    checkpoint_filter = st.sidebar.selectbox(
        "Checkpointy:", options=checkpoint_options, key="checkpoint_filter_selector"
    )

    cols = st.columns([1, 3, 1])

    posts = load_posts(
        db=db,
        team_filter=team_filter,
        challenge_filter=challenge_filter,
        checkpoint_filter=checkpoint_filter,
    )

    col_layout = [5, 2]
    cols = st.columns(col_layout)

    page_size = 10
    page_count = len(posts) // page_size + 1
    page = min(page, page_count - 1)

    center_cols = st.columns([1, 3, 1])

    with center_cols[0]:
        st.title(f"Příspěvky")

    with center_cols[2]:
        st.number_input(
            f"Stránka {page+1}/{page_count}",
            min_value=1,
            max_value=page_count,
            value=page + 1,
            key="page_slider",
            on_change=set_page,
        )

    posts = posts[page * page_size : (page + 1) * page_size]

    for post in posts:
        action_name = post["action_name"]
        action_type = post["action_type"]
        action_id = post.get("action_id")

        team = db.get_team_by_id(post["team_id"])
        description = post["comment"]

        if action_type == "challenge":
            action = db.get_action(action_id, action_type, action_name)
            category = action.get("category")
            action_type_icon = action["category"][0] if category else "💪"

            if action_type_icon.isalpha():
                action_type_icon = "💪"

        elif action_type == "checkpoint":
            action_type_icon = "📍"
        else:
            action_type_icon = "✍️"

        post_id = post["post_id"]
        team_link = db.get_team_link(team)

        link = f"<div style='margin-bottom:-10px; display:inline-block;'><h4><a href='posts?post={post_id}&page={page}&event_id={event_id}' target='_self' class='app-link'>{action_type_icon} {action_name} – {team['team_name']}</a></div>"

        st.markdown(link, unsafe_allow_html=True)
        cols = st.columns(col_layout)
        with cols[0]:
            post_datetime = utils.convert_to_local_timezone(post["created"])
            st.caption(f"*{post_datetime}*")
            st.markdown(
                shorten(utils.escape_html(description), post_id, page),
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

    bottom_cols = st.columns([1, 3, 1])
    if page > 0:
        bottom_cols[0].button("Přechozí", args=(page,), on_click=prev_page)
    if page < page_count - 1:
        bottom_cols[2].button("Další", args=(page,), on_click=next_page)


def main():
    if params.get("post"):
        post = params["post"]
        show_post(db, post)
    else:
        if params.get("page"):
            page = params["page"]
        else:
            page = 0
        show_overview(db=db, page=int(page))


if __name__ == "__page__":
    main()
