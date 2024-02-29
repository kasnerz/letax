import streamlit as st
import utils

st.set_page_config(
    page_title="Stránka účastníka", page_icon="static/favicon.png", layout="wide"
)
from administration import show_admin_page
from user_page import show_user_page
from authenticator import login_page

from database import get_database

params = st.query_params
event_id = utils.get_event_id(params)
db = get_database(event_id=event_id)
st.session_state["event"] = db.get_event()
utils.page_wrapper()

if __name__ == "__main__":
    user, team = login_page()

    if user is None:
        st.stop()

    if user["role"] == "admin":
        show_admin_page(user)
    else:
        _, center_column, _ = st.columns([1, 3, 1])
        with center_column:
            show_user_page(user, team)
