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

utils.page_wrapper()

if __name__ == "__main__":
    user, team = login_page()

    if user is None:
        st.stop()

    # st.query_params["event_id"] = event_id

    if user["role"] == "admin":
        administration.show_admin_page(user)
    else:
        _, center_column, _ = st.columns([1, 3, 1])
        with center_column:
            user_page.show_user_page(user, team)
