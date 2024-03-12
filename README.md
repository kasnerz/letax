# letax

App for **[Letní X-Challenge](x-challenge.cz/letni/)**: a 10-day event full of challenges and low-cost traveling across Europe 🌍️

Organized by **[X-Challenge](https://x-challenge.cz/)**, a Czech non-profit organization and community of people. 🧑‍🤝‍🧑

The app is available to participants during the event at 👉️ **[app.x-challenge.cz](https://app.x-challenge.cz)**.

## Quickstart
1. Clone the repository.
2. Prepare a new Python virtual environment:
```bash
python -m venv venv
source venv/bin/activate
```
3. Install the requirements:
```
pip install -r requirements.txt
```
4. Activate the template files:
```bash
for file in "src/app/accounts.yaml" "src/app/settings.yaml" ".streamlit/secrets.toml"; do
    cp $file{.template,}
done
```
5. Fill in the variables in `.streamlit/secrets.toml` (can be also launched without them with limited functionality).
6. Run the app:
```
./run.sh
```

The app should be accessible through your browser at `http://localhost:7334/`.

You should be able to log in on the user page with the following details:
- login: `admin`
- password: `changethispassword`

(you should of course change the default password)

## Development

A few pointers:
- [Streamlit docs](https://docs.streamlit.io/library/api-reference)
- [my fork of Streamlit Authenticator](https://github.com/kasnerz/Streamlit-Authenticator)
- [Remote SSH in VSCode](https://code.visualstudio.com/docs/remote/ssh)
- [SQLite3 Editor for VSCode](https://marketplace.visualstudio.com/items?itemName=yy0931.vscode-sqlite3-editor)