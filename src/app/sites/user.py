import streamlit as st
import utils

st.set_page_config(
    page_title="Stránka účastníka", page_icon="static/favicon.png", layout="wide"
)
# from administration import show_admin_page
# from user_page import show_user_page

import user_page
import administration
from authenticator import login_page
from database import get_database

if __name__ == "__page__":
    user, team = login_page()

    if user is None:
        st.stop()

    # st.query_params["event_id"] = event_id
    params = st.query_params
    event_id = utils.get_event_id(params)
    db = get_database(event_id=event_id)
    st.session_state["event"] = db.get_event()
    st.session_state["active_event"] = db.get_active_event()
    utils.page_wrapper()

    if user["role"] == "admin":
        administration.show_admin_page(db, user)
    else:
        _, center_column, _ = st.columns([1, 3, 1])
        with center_column:
            user_page.show_user_page(db, user, team)
