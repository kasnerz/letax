#!/usr/bin/env python3

import streamlit as st
import streamlit_authenticator as stauth
import os
import time
import yaml
import utils
from yaml.loader import SafeLoader
import time
import pandas as pd
from database import get_database


st.set_page_config(
    page_title="O aplikaci", page_icon="static/favicon.png", layout="centered"
)

params = st.query_params
event_id = utils.get_event_id(params)
db = get_database(event_id=event_id)
st.session_state["event"] = db.get_event()
utils.page_wrapper()


def main():
    st.title("O a(pli)k(a)ci")

    columns = st.columns([2, 1], gap="large")

    with columns[0]:
        st.markdown(
            """
    Tato appka – **[letax](https://github.com/kasnerz/letax)** (**let**ní **a**ppka **X**-Challenge) – pohání **[Letní X-Challenge](https://x-challenge.cz/letni/)**, akci pořádanou komunitou **[X-Challenge](https://x-challenge.cz/letni/)**. 
    
    Pořádáme i **[spoustu dalších akcí](https://x-challenge.cz/akce/)** a hledáme **[aktivní lidi](https://x-challenge.cz/pridej-se/)**!

"""
        )
        st.markdown(
            """
Za appkou stojí **[Zdeněk Kasner](https://facebook.com/zdenek.kasner/)**, účastník řady X-Challenge akcí. Appku napsal ve volném čase, protože mu to přišlo jako dobrý nápad.

Pokud narazíš na nějakou chybu (a že jich ze začátku může být!), dej mi prosím vědět na **letni@x-challenge.cz**, případně nám napiš na **[Facebook](https://facebook.com/xchallengecz)** nebo **[Instagram](https://instagram.com/xchallengecz/)**.
"""
        )

        st.divider()
        st.markdown(
            """
*© 2023 X-Challenge*
"""
        )
    with columns[1]:
        st.image("static/logo.png", width=200)


if __name__ == "__main__":
    main()
