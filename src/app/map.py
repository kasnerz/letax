import streamlit as st
from database import get_database
import utils
import folium
import datetime
from folium.plugins import BeautifyIcon
from streamlit_folium import folium_static


def show_positions(db):
    # container = st.empty()

    # slider for selecting the date and time in range of the challenge
    event = db.get_active_event()
    event_start_date = event["start_date"]
    event_end_date = event["end_date"]
    start_datetime = f"{event_start_date} 00:00:00"
    end_datetime = f"{event_end_date} 23:59:00"

    start_datetime = datetime.datetime.strptime(start_datetime, "%Y-%m-%d %H:%M:%S")
    end_datetime = datetime.datetime.strptime(end_datetime, "%Y-%m-%d %H:%M:%S")

    st.caption("Poslední nasdílená poloha")
    # slider = st.slider(
    #     "Poslední nasdílená poloha k datu a času",
    #     min_value=start_datetime,
    #     max_value=end_datetime,
    #     value=end_datetime,
    #     step=datetime.timedelta(hours=3),
    #     format="YYYY-MM-DD HH:mm",
    # )

    # for_datetime = slider.strftime("%Y-%m-%d %H:%M:%S")
    for_datetime = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    last_locations = db.get_last_locations(for_datetime=for_datetime)

    if last_locations is None:
        st.info("Žádný tým nezaznamenal svoji polohu")
        st.stop()

    # with container:
    m = folium.Map(
        location=[last_locations.latitude.mean(), last_locations.longitude.mean()],
        zoom_start=4,
        # tiles="Stamen Terrain",
        # tiles="cartodbpositron",
        # tiles="https://mapserver.mapy.cz/turist-m/{z}-{x}-{y}.png",
        attr="<a href=https:/stamen.com/>Stamen.com</a>",
    )

    for _, location in last_locations.iterrows():
        team = db.get_team_by_id(location["team_id"])
        team_icon = team["location_icon"] or "user"
        team_color = team["location_color"] or "red"
        team_icon_color = team["location_icon_color"] or "white"

        team_name = team["team_name"]
        date = location["date"]
        ago_str = utils.ago(date)
        # ago_str = date

        text = "<b>" + team_name + "</b>"

        if location["comment"]:
            popup = f"{location['comment']}<br><br>"
        else:
            popup = ""

        popup += f"<i>{ago_str}</i>"

        icons = db.get_fa_icons()
        icon_type = icons.get(team_icon, "fa-solid")

        folium.Marker(
            [location["latitude"], location["longitude"]],
            popup=popup,
            tooltip=text,
            icon=folium.Icon(
                color=team_color,
                icon=f"{icon_type} fa-{team_icon}",
                icon_color=team_icon_color,
                prefix="fa",
            ),
        ).add_to(m)

    return m, last_locations


def show_last_shared_locations(db, last_locations):
    # show 5 last shared locations
    if last_locations.empty:
        st.info("Žádný tým nezaznamenal svoji polohu")
        st.stop()

    last_locations = last_locations.sort_values(by="date", ascending=False)

    st.subheader("Nedávné aktualizace")

    for _, location in last_locations.head(5).iterrows():
        team = db.get_team_by_id(location["team_id"])
        # team_name = team["team_name"]

        team_link = db.get_team_link(team)

        date = location["date"]
        ago_str = utils.ago(date)
        # ago_str = date

        comment = location.get("comment", "")
        address = location.get("address", "")

        if address:
            address_parts = address.split(",")

            if len(address_parts) > 3:
                address = ", ".join([address_parts[-3], address_parts[-1]])

            address_link = (
                "https://www.google.com/maps/search/?api=1&query="
                + str(location["latitude"])
                + ","
                + str(location["longitude"])
            )
            address_link = f'<a href="{address_link}" target="_blank">{address}</a>'
        else:
            address_link = ""

        text = f"<i>({ago_str})</i><br> <b>{team_link}</b> {comment}<br><i>{address_link}</i>"
        st.markdown(text, unsafe_allow_html=True)


def show_checkpoints(db, m):
    checkpoints = db.get_table_as_df("checkpoints")

    for _, checkpoint in checkpoints.iterrows():
        icon_dot = BeautifyIcon(
            # background_color="darkblue",
            # icon="arrow-down",
            # icon_shape="marker",
            # text_color="white",
            icon_shape="circle-dot",
            border_color="grey",
            border_width=3,
        )
        folium.Marker(
            [checkpoint["latitude"], checkpoint["longitude"]],
            tooltip=checkpoint["name"],
            icon=icon_dot,
        ).add_to(m)


def render_map(m):
    # call to render Folium map in Streamlit
    folium_static(m, width=None, height=500)
