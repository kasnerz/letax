import streamlit as st

dashboard = st.Page("sites/dashboard.py", title="Hlavní stránka", icon="🪧")
posts = st.Page("sites/posts.py", title="Příspěvky", icon="🔵")
leaderboard = st.Page("sites/leaderboard.py", title="Leaderboard", icon="📊")
participants = st.Page("sites/participants.py", title="Účastníci", icon="👣")
teams = st.Page("sites/teams.py", title="Týmy", icon="🧑‍🤝‍🧑")
challenges = st.Page("sites/challenges.py", title="Výzvy", icon="💪")
checkpoints = st.Page("sites/checkpoints.py", title="Checkpointy", icon="📍")
locations = st.Page("sites/locations.py", title="Mapa týmů", icon="🗺️")
user = st.Page("sites/user.py", title="Stránka účastníka", icon="👤")
archive = st.Page("sites/archive.py", title="Archiv", icon="📔")
about = st.Page("sites/about.py", title="O aplikaci", icon="💡")


pg = st.navigation(
    {
        "Aktuálně": [
            dashboard,
            posts,
            leaderboard,
            participants,
            teams,
            challenges,
            checkpoints,
            locations,
        ],
        "Pro účastníky": [
            user,
        ],
        "Další": [
            archive,
            about,
        ],
    }
)

pg.run()
