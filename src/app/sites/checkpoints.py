#!/usr/bin/env python3

import streamlit as st
import pandas as pd
from database import get_database
import utils
from unidecode import unidecode
from slugify import slugify

st.set_page_config(
    page_title="Checkpointy", page_icon="static/favicon.png", layout="wide"
)

from authenticator import login_page

params = st.query_params
event_id = utils.get_event_id(params)
db = get_database(event_id=event_id)
st.session_state["event"] = db.get_event()
st.session_state["active_event"] = db.get_active_event()
utils.page_wrapper()


def main():
    st.title("Checkpointy")

    gmaps_url = db.get_gmaps_url(event_id)
    checkpoints = db.get_table_as_df("checkpoints")

    if checkpoints.empty:
        st.info("Na tento ročník zatím checkpointy nejsou. Ale budou!")
        st.stop()

    available_actions = [x["id"] for x in db.get_available_actions(user, "checkpoint")]

    # sort by name
    checkpoints = checkpoints.sort_values(
        by="name", key=lambda x: [unidecode(a) for a in x]
    )

    # generate urls
    checkpoints["url"] = checkpoints.apply(
        lambda x: f"http://www.google.com/maps/place/{x['latitude']},{x['longitude']}",
        axis=1,
    )
    checkpoints["Splněno"] = checkpoints.apply(
        lambda x: "✔️" if x["id"] not in available_actions else "-", axis=1
    )

    checkpoints["link"] = checkpoints.apply(
        lambda x: f"<a href='{x['url']}' target='_blank'>{x['name']}</a>",
        axis=1,
    )
    tabs = st.tabs(["Seznam", "Popis", "Mapa"])

    with tabs[0]:
        # name and points, no index
        # rename columns: name->Název, points->Body
        checkpoints_table = checkpoints.rename(
            columns={"link": "Název", "points": "Body"}
        )
        checkpoints_table = checkpoints_table.reset_index(drop=True)
        if "points_challenge" in checkpoints_table.columns:
            # change the "Body" column to include challenge points
            checkpoints_table["Body"] = checkpoints_table.apply(
                lambda x: f"{x['Body']} + {x['points_challenge']}"
                if pd.notna(x["points_challenge"]) and x["points_challenge"] > 0
                else x["Body"],
                axis=1,
            )
        checkpoints_table = checkpoints_table[["Název", "Body", "Splněno"]]
        # checkpoints_table.style.set_table_attributes('class="full-width"')

        # set max width
        st.write(
            checkpoints_table.to_html(
                escape=False, classes="table-display", index=False
            ),
            unsafe_allow_html=True,
        )

    with tabs[1]:
        for _, checkpoint in checkpoints.iterrows():
            checkpoint_url = checkpoint["url"]
            # slug = slugify(checkpoint["name"])

            if checkpoint.get("points_challenge"):
                points = f"{checkpoint['points']} + {checkpoint['points_challenge']}"
            else:
                points = checkpoint["points"]

            link = f"<div style='margin-bottom:-10px; display:inline-block;'><a  href='{checkpoint_url}' style='text-decoration: none;'><h4 class='app-link'>{checkpoint['name']} ({points})</b></h4></a></div>"
            st.markdown(link, unsafe_allow_html=True)
            # st.caption(f", ")
            st.markdown(f"{checkpoint['description']}")
            # st.markdown("##### Výzva")
            st.markdown(f"**Výzva:** *{checkpoint['challenge']}*")
            st.divider()

    with tabs[2]:
        st.markdown(
            f"""
        <iframe
            width="100%"
            height="480"
            frameborder="0" style="border:0"
            src="{gmaps_url}"
            allowfullscreen
            >
        </iframe>
        """,
            unsafe_allow_html=True,
        )

    #     # st.components.v1.iframe(gmaps_url, width=500, height=480, scrolling=False)

    #     st.markdown(
    #         f"""
    #     <iframe
    #         width="100%"
    #         height="480"
    #         frameborder="0" style="border:0"
    #         src="{gmaps_url}"
    #         allowfullscreen
    #         sandbox="allow-same-origin"
    #         >
    #     </iframe>
    #     """,
    #         unsafe_allow_html=True,
    #     )


if __name__ == "__main__":
    user, team = login_page()

    if user:
        cols = st.columns([1, 3, 1])
        with cols[1]:
            main()
