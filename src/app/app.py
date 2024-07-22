import streamlit as st

dashboard = st.Page("sites/dashboard.py", title="Hlavní stránka", icon="🪧")
posts = st.Page("sites/posts.py", title="Příspěvky", icon="🔵")
participants = st.Page("sites/participants.py", title="Účastníci", icon="👣")
teams = st.Page("sites/teams.py", title="Týmy", icon="🧑‍🤝‍🧑")
challenges = st.Page("sites/challenges.py", title="Výzvy", icon="💪")
checkpoints = st.Page("sites/checkpoints.py", title="Checkpointy", icon="📍")
map = st.Page("sites/map.py", title="Mapa týmů", icon="🗺️")
user = st.Page("sites/user.py", title="Stránka účastníka", icon="👤")
archive = st.Page("sites/archive.py", title="Archiv", icon="📔")
about = st.Page("sites/about.py", title="O aplikaci", icon="💡")

pg = st.navigation(
    [
        dashboard,
        posts,
        participants,
        teams,
        challenges,
        checkpoints,
        map,
        user,
        archive,
        about,
    ]
)

pg.run()
