import streamlit as st
import utils

st.set_page_config(
    page_title="Stránka účastníka", page_icon="static/favicon.png", layout="wide"
)
utils.page_wrapper()

from administration import show_admin_page
from user_page import show_user_page
from authenticator import login_page

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
