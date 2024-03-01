#!/usr/bin/env python3

from datetime import datetime
from PIL import Image, ImageOps
from slugify import slugify
from unidecode import unidecode
from woocommerce import API
from accounts import AccountManager

from zipfile import ZipFile
from gpxpy.gpx import GPX, GPXRoute, GPXRoutePoint, GPXWaypoint
from geopy.geocoders import Nominatim

import argparse
import boto3
import csv
import io
import json
import logging
import mimetypes
import os
import pandas as pd
import re
import s3fs
import sqlite3
import streamlit as st
import utils
import yaml
import zipfile
import base64
import copy
import locale

import shutil
import tempfile
import ast
import dateutil.parser

# logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

current_dir = os.path.dirname(os.path.realpath(__file__))


# TODO find a way how to retrieve this value from the config
TTL = 3600 * 24


@st.cache_resource
def get_database(event_id=None):
    # if event_id is none, the active event is used
    return Database(event_id)


class Database:
    def __init__(self, event_id=None):
        self.settings_path = os.path.join(current_dir, "settings.yaml")
        self.load_settings()

        self.wcapi = API(
            url="https://x-challenge.cz/",
            consumer_key=st.secrets["woocommerce"]["consumer_key"],
            consumer_secret=st.secrets["woocommerce"]["consumer_secret"],
            version="wc/v3",
            timeout=30,
        )
        self.event = self.get_event_by_id(event_id)
        self.conn = self.get_db_for_event(self.event["id"])

        if self.get_settings_value("file_system") == "s3":
            # S3 bucket
            # used as a filesystem for the database
            self.fs = s3fs.S3FileSystem(anon=False)
            self.fs_bucket = self.get_settings_value("fs_bucket")
            self.boto3 = boto3.resource(
                "s3",
                region_name=st.secrets["AWS_DEFAULT_REGION"],
                aws_access_key_id=st.secrets["AWS_ACCESS_KEY_ID"],
                aws_secret_access_key=st.secrets["AWS_SECRET_ACCESS_KEY"],
            )
        self.top_dir = f"files/{self.event['id']}"
        self.am = AccountManager()
        self.preauthorized_emails = self.load_preauthorized_emails()
        self.static_imgs = self.load_static_images()
        self.fa_icons = self.load_fa_icons()
        self.geoloc = Nominatim(user_agent="GetLoc")

        utils.log("Database initialized")

    def __del__(self):
        self.conn.close()

    def get_events(self):
        return sorted(
            self.get_settings_value("events"), key=lambda x: x["year"], reverse=True
        )

    def get_event_by_id(self, event_id):
        events = self.get_events()

        if event_id:
            events = [e for e in events if e["id"] == event_id]
        elif any(e["status"] == "active" for e in events):
            events = [e for e in events if e["status"] == "active"]
        else:
            # find the most recent `past` event
            events = [e for e in events if e["status"] == "past"]

        if not events:
            raise ValueError(f"Event {event_id} not found")

        return events[0]

    def get_db_for_event(self, event_id):
        os.makedirs(os.path.join("db", event_id), exist_ok=True)
        self.db_path = os.path.join("db", event_id, "database.db")

        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.create_tables()

        return self.conn

    def get_year(self, event_id=None):
        if event_id:
            event = self.get_event_by_id(event_id)
            return event["year"]

        return self.event["year"]

    def get_gmaps_url(self, event_id=None):
        event = self.get_event_by_id(event_id)
        return event["gmaps_url"]

    def get_event(self):
        return self.event

    def create_new_event(self, year):
        events = self.get_events()
        new_event_id = utils.generate_uuid()
        events.append(
            {
                "id": new_event_id,
                "year": year,
                "status": "draft",
                "gmaps_url": "",
                "product_id": "",
            }
        )
        self.set_settings_value("events", events)

    def set_event_info(self, event_id, status, gmaps_url, product_id):
        events = self.get_events()
        for event in events:
            if event["id"] == event_id:
                event["status"] = status
                event["gmaps_url"] = gmaps_url
                event["product_id"] = product_id
                break

        self.set_settings_value("events", events)

    def load_settings(self):
        with open(self.settings_path) as f:
            self.settings = yaml.safe_load(f)

    def get_settings_value(self, key):
        return self.settings.get(key)

    def set_settings_value(self, key, value):
        self.settings[key] = value
        self.save_settings()

    def save_settings(self):
        with open(self.settings_path, "w") as f:
            yaml.dump(self.settings, f)

    def load_static_images(self):
        static_images = {"topx.png": None}

        for filename in static_images.keys():
            with open(f"static/{filename}", "rb") as f:
                contents = f.read()
                data_url = base64.b64encode(contents).decode("utf-8")
                static_images[filename] = data_url

        return static_images

    def get_static_image_base64(self, filename):
        return self.static_imgs.get(filename)

    def load_fa_icons(self):
        with open("static/fa_icons.json") as f:
            fa_icons = json.load(f)

        return fa_icons

    def restore_backup(self, backup_file):
        zip_path = os.path.join("backups", backup_file)

        if not os.path.exists(zip_path):
            raise ValueError(f"Backup file {zip_path} does not exist.")

        # overwrite the database in db folder and the accounts in src/app/accounts.yaml by unzipping the backup
        # the zip file contains the folders db/ and src/
        with zipfile.ZipFile(zip_path, "r") as zip_ref:
            zip_ref.extractall(".")

        # reload the database
        self.__init__()
        utils.clear_cache()

    # @st.cache_resource(ttl=TTL, show_spinner=False)
    def get_boto3_object(_self, filepath):
        obj = _self.boto3.Object(_self.fs_bucket, filepath)
        return obj

    # @st.cache_resource(ttl=TTL, max_entries=50, show_spinner=False)
    def read_file(_self, filepath, mode="b"):
        fs = _self.get_settings_value("file_system")
        if fs == "s3" and not filepath.startswith("static/"):
            # use boto3 to get the S3 object
            try:
                obj = _self.get_boto3_object(filepath)
                # read the contents of the file and return
                content = obj.get()["Body"].read()

                # text files need decoding
                if mode == "t":
                    return content.decode("utf-8")

                return content
            except Exception as e:
                return None

        elif fs == "local" or filepath.startswith("static/"):
            # if does not exist, return None
            if not os.path.exists(filepath):
                return None
            with open(filepath, "r" + mode) as f:
                return f.read()
        else:
            raise ValueError(f"Unknown file system: {fs}, use s3 or local.")

    def delete_file(self, filepath):
        fs = self.get_settings_value("file_system")
        if fs == "s3" and not filepath.startswith("static/"):
            # use boto3 to get the S3 object
            try:
                obj = self.get_boto3_object(filepath)
                obj.delete()
            except Exception as e:
                utils.log(str(e), level="error")
                return None

        elif fs == "local" or filepath.startswith("static/"):
            os.remove(filepath)
        else:
            raise ValueError(f"Unknown file system: {fs}, use s3 or local.")

    def save_thumbnail(self, filepath, img):
        img_byte_array = io.BytesIO()
        img = img.convert("RGB")
        img.save(img_byte_array, format="JPEG")
        img_bytes = img_byte_array.getvalue()

        self.write_file(filepath, img_bytes)

    def create_thumbnails(self, img, filepath):
        # utils.log(f"Creating thumbnails for {filepath}.", level="debug")
        filepath = os.path.splitext(filepath)[0]

        img_100 = utils.resize_image(img, max_width=100, crop_ratio="1:1")
        self.save_thumbnail(f"{filepath}_100_square.jpg", img_100)

        img_150 = utils.resize_image(img, max_width=150, crop_ratio="1:1")
        self.save_thumbnail(f"{filepath}_150_square.jpg", img_150)

        img_1000 = utils.resize_image(img, max_width=1000)
        self.save_thumbnail(f"{filepath}_1000.jpg", img_1000)

    # @st.cache_resource(max_entries=1, show_spinner=False)
    def read_video(_self, filepath):
        return _self.read_file(filepath, mode="b")

    # @st.cache_resource(max_entries=500, show_spinner=False)
    def read_image(_self, filepath, thumbnail=None):
        # TODO simplify
        file_extension = os.path.splitext(filepath)[1]

        thumbnail_size = thumbnail or "100_square"  # 100_square is just for the checks
        thumbnail_filepath = filepath.replace(file_extension, f"_{thumbnail_size}.jpg")
        thumbnail_img = _self.read_file(thumbnail_filepath, mode="b")

        # if there are no thumbnails for the current image, create the thumbnails
        if not thumbnail_img:
            # try to find a thumbnail of a suitable size:
            img = _self.read_file(filepath, mode="b")

            if not img:
                utils.log(f"Cannot load image: {filepath}", level="error")
                # return blank image
                return Image.new("RGB", (1, 1))

            # read image using PIL
            try:
                img = Image.open(io.BytesIO(img))
                img = ImageOps.exif_transpose(img)
            except Exception as e:
                utils.log(f"Cannot read image: {filepath}", level="error")
                # return blank image
                return Image.new("RGB", (1, 1))

            # if the image was successfully loaded, create thumbnails
            _self.create_thumbnails(img, filepath)

            try:
                thumbnail_img = _self.read_file(thumbnail_filepath, mode="b")
            except:
                utils.log(f"Cannot load thumbnail: {thumbnail_filepath}", level="error")
                # return blank image
                return Image.new("RGB", (1, 1))

        if thumbnail:
            filepath = thumbnail_filepath
            img = thumbnail_img
        else:
            img = _self.read_file(filepath, mode="b")

        # read image using PIL
        try:
            img = Image.open(io.BytesIO(img))
            img = ImageOps.exif_transpose(img)
        except Exception as e:
            utils.log(f"Cannot read image: {filepath}", level="error")
            # return blank image
            return Image.new("RGB", (1, 1))

        return img

    def write_file(self, filepath, content):
        fs = self.get_settings_value("file_system")

        if fs == "s3" and not filepath.startswith("static/"):
            self.boto3.Object(self.fs_bucket, filepath).put(Body=content)
        elif fs == "local" or filepath.startswith("static/"):
            mode = "t" if type(content) == str else "b"

            os.makedirs(os.path.dirname(filepath), exist_ok=True)

            with open(filepath, "w" + mode) as f:
                return f.write(content)

    def wc_get_all_orders(self, product_id):
        page = 1
        orders = []
        has_more_orders = True

        while has_more_orders:
            params = {
                "product": product_id,
                # "per_page": 10,
                "per_page": 100,
                "page": page,
            }
            # Make the API request to retrieve a batch of orders

            response = self.wcapi.get("orders", params=params)
            response = response.json()

            # Check if there are any orders in the response
            if len(response) > 0:
                # Add the retrieved orders to the list
                orders.extend(response)

                # Increment the page number for the next request
                page += 1
            else:
                # No more orders, exit the loop
                has_more_orders = False

        return orders

    def wc_fetch_participants(self, log_area=None, limit=None):
        product_id = self.event["product_id"]
        new_participants = []
        logger.info("Fetching participants from WooCommerce...")

        # print all existing participants
        for row in self.conn.execute("SELECT * FROM participants"):
            utils.log(str(dict(row)), level="debug")

        # TODO fetch only orders after last update
        orders = self.wc_get_all_orders(product_id=product_id)
        utils.log(f"Found {len(orders)} orders", level="info")

        if log_area:
            st.write(f"Nalezeno {len(orders)} objednávek")
            pb = st.progress(value=0, text="Načítám info o účastnících")

        user_ids = [user["customer_id"] for user in orders][:limit]

        for i, user_id in enumerate(user_ids):
            logger.info(f"Fetching user {user_id}")
            response = self.wcapi.get("customers/" + str(user_id))
            response = response.json()
            new_participants.append(response)

            if log_area:
                total_paxes = len(user_ids)
                if limit:
                    total_paxes = min(limit, total_paxes)

                pb.progress(
                    i / float(len(user_ids)),
                    f"Načítám info o účastnících ({i}/{total_paxes})",
                )

        with open("wc_participants.json", "w") as f:
            json.dump(new_participants, f)

        self.add_participants(new_participants)
        self.load_preauthorized_emails()

        utils.clear_cache()

        pb.progress(1.0, "Hotovo!")

    def load_preauthorized_emails(self):
        participants = self.get_participants(include_non_registered=True)

        emails = []
        if not participants.empty:
            # extract the field `email` from pandas df
            emails = list(participants.email)

        extra_allowed_emails = list(self.am.get_extra_accounts().keys())
        preauthorized = {"emails": [e.lower() for e in emails + extra_allowed_emails]}

        return preauthorized

    def get_preauthorized_emails(self):
        return self.preauthorized_emails

    def add_extra_participant(self, email, name):
        # generate a random integer id
        user_id = utils.generate_uuid()
        email = email.lower()

        self.conn.execute(
            "INSERT OR IGNORE INTO participants (id, email, name_web) VALUES (?, ?, ?)",
            (user_id, email, name),
        )
        self.conn.commit()

        utils.log(f"Added extra participant {email} ({name})", level="success")

    def add_participants(self, new_participants):
        for user in new_participants:
            user_data = (
                str(int(user["id"])),
                user["email"],
                user["first_name"].title() + " " + user["last_name"].title(),
            )

            self.conn.execute(
                "INSERT OR IGNORE INTO participants (id, email, name_web) VALUES (?, ?, ?)",
                user_data,
            )
            self.conn.commit()

    def wc_get_user_by_email(self, email):
        query = "SELECT * FROM participants WHERE email = ?"
        return self.conn.execute(query, (email,)).fetchone()

    def get_participants(
        self, sort_by_name=True, include_non_registered=False, fetch_teams=False
    ):
        # the table `participants` include only emails
        # we need to join this with the user accounts

        participants = []
        query = "SELECT * FROM participants"

        for pax_info in self.conn.execute(query).fetchall():
            pax_info = dict(pax_info)
            user_info = self.am.get_user_by_email(pax_info["email"])
            if user_info:
                pax_info.update(user_info)

            if not pax_info.get("name"):
                pax_info["name"] = pax_info["name_web"]

            if not pax_info.get("username"):
                pax_info["username"] = pax_info["name"]

            # if `return_non_registered` is true, return all participants, otherwise only those for which we have info
            if include_non_registered or user_info:
                participants.append(pax_info)

        participants = pd.DataFrame(participants)

        if not participants.empty and sort_by_name:
            # considering unicode characters in Czech alphabet
            participants = participants.sort_values(
                by="name", key=lambda x: [unidecode(a).lower() for a in x]
            )

        if fetch_teams and not participants.empty:
            teams = self.get_table_as_df("teams")
            # participant is either member1 or member2, if not - no team
            pax_id_to_team = {
                str(row["member1"]): row
                for _, row in teams.iterrows()
                if row["member1"]
            }
            pax_id_to_team.update(
                {
                    str(row["member2"]): row
                    for _, row in teams.iterrows()
                    if row["member2"]
                }
            )

            participants["team_name"] = participants.apply(
                lambda x: pax_id_to_team.get(str(x["id"]), {}).get("team_name"), axis=1
            )
            participants["team_id"] = participants.apply(
                lambda x: pax_id_to_team.get(str(x["id"]), {}).get("team_id"), axis=1
            )

        return participants

    def is_participant(self, email):
        query = "SELECT * FROM participants WHERE email = ?"
        return self.conn.execute(query, (email,)).fetchone() is not None

    def get_participant_by_id(self, id):
        query = "SELECT * FROM participants WHERE id = ?"
        pax_info = self.conn.execute(query, (id,)).fetchone()

        if not pax_info:
            return None

        pax_info = dict(pax_info)
        user_info = self.am.get_user_by_email(pax_info["email"])
        if user_info:
            pax_info.update(user_info)

        if not pax_info.get("name"):
            pax_info["name"] = pax_info["name_web"]

        if not pax_info.get("username"):
            pax_info["username"] = pax_info["name"]

        return pax_info

    def get_participant_by_email(self, email):
        query = "SELECT * FROM participants WHERE email = ?"
        return self.conn.execute(query, (email,)).fetchone()

    def update_participant(self, username, email, bio, emergency_contact, photo=None):
        if photo is None:
            query = (
                "UPDATE participants SET bio = ?, emergency_contact = ? WHERE email = ?"
            )
            self.conn.execute(query, (bio, emergency_contact, email))
            self.conn.commit()

        else:
            query = "UPDATE participants SET bio = ?, emergency_contact = ?, photo = ? WHERE email = ?"

            dir_path = os.path.join(self.top_dir, "participants", slugify(username))

            photo_content, photo_name = utils.postprocess_uploaded_photo(photo)

            photo_path = os.path.join(dir_path, photo_name)

            self.write_file(
                filepath=os.path.join(dir_path, photo_name), content=photo_content
            )

            self.conn.execute(query, (bio, emergency_contact, photo_path, email))
            self.conn.commit()

            utils.log(f"Updated info for {username}", level="info")

    def get_table_as_df(self, table_name):
        df = pd.read_sql_query(f"SELECT * FROM {table_name}", self.conn)
        return df

    def save_df_as_table(self, df, table_name):
        # remove rows containing **ONLY** NaNs
        df = df.dropna(how="all")

        df.to_sql(table_name, self.conn, if_exists="replace", index=False)

    def get_post_by_id(self, post_id):
        query = "SELECT * FROM posts WHERE post_id = ?"
        post = self.conn.execute(query, (post_id,)).fetchone()

        if not post:
            return None

        post = dict(post)
        post["files"] = json.loads(post["files"])
        return post

    def get_posts_by_team(self, team_id):
        df = pd.read_sql_query(
            f"SELECT * FROM posts WHERE team_id = ?", self.conn, params=(team_id,)
        )
        return df

    def save_post(self, user, action_type, action, comment, files):
        team = self.get_team_for_user(user["pax_id"])
        # save all the files to the filesystem

        title = action if action_type == "story" else action["name"]

        dir_path = os.path.join(
            self.top_dir, action_type, slugify(title), slugify(team["team_name"])
        )

        files_json = []

        # show progress in streamlit
        # progress_bar = st.progress(0)

        for i, file in enumerate(files):
            # if it's a photo, we need to process it
            if file.type.startswith("image"):
                file_content, file_name = utils.postprocess_uploaded_photo(file)
            elif file.type.startswith("video"):
                file_content, file_name = utils.postprocess_uploaded_video(file)

                # ... ignore the rest

            file_path = os.path.join(dir_path, file_name)
            self.write_file(filepath=file_path, content=file_content)

            # TODO return type from postprocessing
            files_json.append({"path": file_path, "type": file.type})

            # progress_bar.progress((i + 1) / len(files))

        post_id = utils.generate_uuid()

        # serialize files as json string
        files_json = json.dumps(files_json)
        created = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        pax_id = user["pax_id"]
        team_id = str(team["team_id"])

        self.conn.execute(
            f"INSERT INTO posts (post_id, pax_id, team_id, action_type, action_name, comment, files, created) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                post_id,
                pax_id,
                team_id,
                action_type,
                title,
                comment,
                files_json,
                created,
            ),
        )
        self.conn.commit()

        utils.log(
            f"{user['username']} ({team['team_name']}) added post '{title}'",
            level="success",
        )

    def generate_post_html(self, post, output_dir, aws_prefix=None):
        photos_html = ""

        post_title = post["action_name"]
        description = post["comment"]
        files = ast.literal_eval(post["files"])

        if post["action_type"] == "challenge":
            post_title = f"🏆 {post_title}"
        elif post["action_type"] == "checkpoint":
            post_title = f"📍 {post_title}"
        else:
            post_title = f"✍️ {post_title}"

        post_datetime = utils.convert_to_local_timezone(post["created"])
        post_datetime = dateutil.parser.parse(post_datetime)

        # convert to the format "26. srpna 2023, 15:00"
        current_locale = locale.getlocale()
        locale.setlocale(locale.LC_TIME, "cs_CZ.UTF-8")
        post_datetime = post_datetime.strftime("%x %X")
        locale.setlocale(locale.LC_TIME, current_locale)

        if description:
            # escape html
            description = utils.escape_html(description)

        # images = [f for f in files if f["type"].startswith("image")]
        # videos = [f for f in files if f["type"].startswith("video")]

        os.makedirs(os.path.join(output_dir, "files"), exist_ok=True)

        photos_html = "<div class='container'><div class='row'>"
        for file in files:
            file_type = "image" if file["type"].startswith("image") else "video"
            if not aws_prefix:
                # copy files locally
                filename = os.path.join("files", os.path.basename(file["path"]))

                if file_type == "image":
                    file = self.read_image(file["path"], thumbnail="1000")
                    file.save(os.path.join(output_dir, filename))
                else:
                    file = self.read_video(file["path"])
                    with open(os.path.join(output_dir, filename), "wb") as f:
                        f.write(file)
                href = filename
            else:
                href = f"{aws_prefix}/{file['path']}"

            if file_type == "image":
                photos_html += f'<div class="col-3"><a href="{href}" data-toggle="lightbox" data-gallery="{post["post_id"]}"><img data-src="{href}" class="image img-thumbnail lazyload"></a></div>'
            else:
                photos_html += f'<div class="col-3"><a href="{href}" data-toggle="lightbox" data-gallery="{post["post_id"]}"><video src="{href}" preload="none" controls class="video"></video></a></div>'

        photos_html += "</div></div>"

        return f"""
                <div class="card mb-3 lazyload">
                    <div class="card-header">
                    <h3>{post_title}</h3>
                    <h6>{post_datetime}</h6>
                    </div>
                    <div class="card-body ">
                    <p class="card-text">{description}</p>
                    {photos_html}
                    </div>
                </div>
                """

    def generate_team_posts_html(self, team, output_dir, xc_year, aws_prefix=None):
        utils.log(f"Exporting posts for team {team['team_name']}", level="info")
        posts = self.get_posts_by_team(team["team_id"])

        title = f"{team['team_name']} – Letní X-Challenge {xc_year}"
        post_html = ""
        for _, post in posts.iterrows():
            post_html += self.generate_post_html(
                post, output_dir, aws_prefix=aws_prefix
            )

        with open("static/website_export/custom.css") as f:
            css = f.read()

        # use Source Sans Pro font, bold for headings
        html = f"""
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <!-- Back button -->
            <a href="../../index.html" class="btn btn-outline-dark" style="margin-top: 20px;">← Zpět na výsledky</a>
            <title>{title}</title>
            <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap@5.2.3/dist/css/bootstrap.min.css">
            <link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Source+Sans+Pro:wght@400;600;700&display=swap">
        </head>
        <body>
            <style>{css}</style>
            <div class="container mt-3">
            <h1>{title}</h1>
            {post_html}
            </div>
            <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.2.3/dist/js/bootstrap.bundle.min.js"></script>
            <script src="https://cdn.jsdelivr.net/npm/bs5-lightbox@1.8.3/dist/index.bundle.min.js"></script>
            <script src="https://cdn.jsdelivr.net/npm/lazyload@2.0.0-rc.2/lazyload.js"></script>
            <script>
            lazyload();
            </script>
        </body>
        </html>
        """
        with open(os.path.join(output_dir, "index.html"), "w") as f:
            f.write(html)

    def export_team_posts(self, team, output_dir, xc_year, folder_name):
        tmp_filename = f"post_{team['team_id']}.zip"

        with ZipFile(os.path.join(output_dir, tmp_filename), "w") as zip_file:
            for root, _, files in os.walk(output_dir):
                for file in files:
                    if file != tmp_filename:  # Exclude the zip file itself
                        file_path = os.path.join(root, file)
                        archive_name = os.path.relpath(file_path, output_dir)
                        archive_name = os.path.join(folder_name, archive_name)
                        zip_file.write(file_path, archive_name)

        utils.log(
            f"Exported posts for team {team['team_name']} to {output_dir}/{tmp_filename}",
            level="success",
        )
        return os.path.join(output_dir, tmp_filename)

    def generate_static_page(self, output_dir, teams, xc_year):
        title = f"Letní X-Challenge {xc_year}"

        for i, team in enumerate(teams):
            posts = team["posts"]
            posts["action_type"].value_counts()
            for action_type in ["challenge", "checkpoint", "story"]:
                teams[i][action_type] = (
                    posts["action_type"].value_counts().get(action_type, 0)
                )
        table = pd.DataFrame(
            teams,
            columns=[
                "team_name",
                "points",
                "team_id",
                "member1_name",
                "member2_name",
                "challenge",
                "checkpoint",
                "story",
            ],
        )
        table = table.sort_values(by="points", ascending=False)
        table = table.reset_index(drop=True)

        # Round points to integers
        table["points"] = table["points"].astype(int)
        table = table.rename(
            columns={
                "team_name": "Tým",
                "member1_name": "Člen 1",
                "member2_name": "Člen 2",
                "points": "Body",
                "challenge": "Výzvy",
                "checkpoint": "Checkpointy",
                "story": "Příspěvky",
            }
        )

        # table.index += 1
        # table.index.name = "Pořadí"
        # Generate HTML code for the table

        with open("static/website_export/custom.css") as f:
            css = f.read()

        html_code = f"""
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <a href="../index.html" class="btn btn-outline-dark" style="margin-top: 20px;">← Zpět na seznam akcí</a>
            <title>{title}</title>
            <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap@5.2.3/dist/css/bootstrap.min.css" crossorigin="anonymous">
            <link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Source+Sans+Pro:wght@400;600;700&display=swap">
        </head>
        <body>
            <style>{css}</style>
            <div class="container">
                <h1>{title}</h1>
                <p>{title} je za námi! Zde si můžeš prohlédnout výsledky a příspěvky týmů.</p>
                <table class="table table-bordered table-striped">
                    <thead>
                        <tr>
                            <th>Pořadí</th>
                            """

        # Add table headers
        for col in table.columns:
            if col == "team_id":
                continue
            html_code += f"<th>{col}</th>"

        html_code += """
                        </tr>
                    </thead>
                    <tbody>
                        """

        # Add table rows
        for index, row in table.iterrows():
            html_code += f"<tr>\n<td>{index+1}</td>"
            for col in table.columns:
                if col == "Tým":
                    # Add link according to the team_id
                    html_code += f"<td><a href='teams/{row['team_id']}/index.html'>{row[col]}</a></td>"
                elif col == "team_id":
                    continue
                else:
                    html_code += f"<td>{row[col]}</td>"
            html_code += "</tr>\n"

        html_code += """
                    </tbody>
                </table>
            </div>
            <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.2.3/dist/js/bootstrap.bundle.min.js" crossorigin="anonymous"></script>
        </body>
        </html>
        """

        with open(os.path.join(output_dir, "index.html"), "w") as f:
            f.write(html_code)

    def export_static_website(self, output_dir):
        aws_prefix = "https://s3.eu-west-3.amazonaws.com/xchallengecz"
        teams = self.get_teams_overview()

        event_id = self.event["id"]
        xc_year = self.event["year"]

        os.makedirs(os.path.join(output_dir, event_id, "teams"), exist_ok=True)

        for i, team in enumerate(teams):
            team_out_dir = os.path.join(output_dir, event_id, "teams", team["team_id"])
            os.makedirs(team_out_dir, exist_ok=True)

            self.generate_team_posts_html(
                team, team_out_dir, event_id, aws_prefix=aws_prefix
            )

        self.generate_static_page(os.path.join(output_dir, event_id), teams, xc_year)
        utils.log(f"Exported static website to {output_dir}", level="success")

    def get_team_by_id(self, team_id):
        # retrieve team from the database, return a single Python object or None
        query = "SELECT * FROM teams WHERE team_id = ?"
        ret = self.conn.execute(query, (team_id,))
        team = ret.fetchone()
        return team

    def get_team_for_user(self, pax_id):
        if pax_id is None:
            return None

        # the field `member1`, `member2`  contains the id
        query = "SELECT * FROM teams WHERE member1 = ? OR member2 = ?"
        ret = self.conn.execute(query, (pax_id, pax_id))
        team = ret.fetchone()

        return team

    def get_teams_with_awards(self):
        # any team that has a non-empty award column (non-empty = NULL or "")
        return pd.read_sql_query(
            "SELECT * FROM teams WHERE (award IS NOT NULL AND award != '')", self.conn
        )

    def set_team_award(self, team_id, award):
        self.conn.execute(
            "UPDATE teams SET award = ? WHERE team_id = ?", (award, team_id)
        )
        self.conn.commit()
        utils.log(f"Set award {award} for team {team_id}", level="info")

    def get_action(self, action_type, action_name):
        # retrieve action from the database, return a single Python object or None
        table_name = {
            "challenge": "challenges",
            "checkpoint": "checkpoints",
        }[action_type]

        if not table_name:
            return None

        # get action that starts with `action_name`
        # solves "Denní výzva #1" vs. "Denní výzva #1 - blabla"
        query = f"SELECT * FROM {table_name} WHERE name LIKE ?"
        ret = self.conn.execute(query, (action_name + "%",))
        action = ret.fetchone()
        return dict(action) if action else None

    def get_points_for_action(self, action_type, action_name):
        if action_type == "story":
            return 0

        action = self.get_action(action_type, action_name)

        if not action:
            utils.log(f"Action {action_name} not found", level="warning")
            return 0

        pts = action.get("points", 0)

        return pts

    def get_team_overview(self, team_id, posts, participants):
        # filter posts by team_id
        posts_team = posts[posts["team_id"] == team_id]

        # for each post, find a particular action by its `action_name` in the table `challenges`, `checkpoints`, etc. (determined according its action_type) and add the number of points to the post

        # Use the apply() function to apply the get_points function to each row in the DataFrame
        if not posts_team.empty:
            posts_team = posts_team.assign(
                points=posts_team.apply(
                    lambda row: self.get_points_for_action(
                        row["action_type"], row["action_name"]
                    ),
                    axis=1,
                )
            )
        team = self.get_team_by_id(team_id)

        member1_name = participants[participants["id"] == team["member1"]].to_dict(
            "records"
        )[0]
        member1_name = member1_name["name"]

        member2_name = ""
        if team["member2"]:
            member2_name = participants[participants["id"] == team["member2"]].to_dict(
                "records"
            )[0]
            member2_name = member2_name["name"]

        team_info = {
            "team_id": team_id,
            "team_name": team["team_name"],
            "member1": team["member1"],
            "member1_name": member1_name,
            "member2": team["member2"],
            "member2_name": member2_name,
            "points": posts_team["points"].sum() if not posts_team.empty else 0,
            "posts": posts_team,
            "award": team["award"],
            "is_top_x": team["is_top_x"],
            "team_photo": team["team_photo"],
            "team_motto": team["team_motto"],
            "team_web": team["team_web"],
        }
        return team_info

    def get_teams_overview(self):
        teams = self.get_table_as_df("teams")
        posts = self.get_table_as_df("posts")
        participants = self.get_participants(
            include_non_registered=True, sort_by_name=False
        )

        # get team overview for each team
        teams_info = [
            self.get_team_overview(team_id, posts, participants)
            for team_id in teams["team_id"]
        ]

        return teams_info

    def get_posts(
        self, team_filter=None, challenge_filter=None, checkpoint_filter=None
    ):
        # team_filter is the team_name, the table posts contain only id -> join with teams table to get the team_name
        posts = self.get_table_as_df("posts")
        teams = self.get_table_as_df("teams")
        posts = posts.merge(teams, on="team_id")

        if team_filter:
            posts = posts[posts["team_name"] == team_filter]

        if challenge_filter:
            posts = posts[posts["action_name"] == challenge_filter]

        if checkpoint_filter:
            posts = posts[posts["action_name"] == checkpoint_filter]

        # convert files from json string to Python object
        posts["files"] = posts["files"].apply(lambda x: json.loads(x))
        # convert df to list with dicts
        posts = posts.to_dict("records")
        return posts

    def update_post_comment(self, post_id, comment):
        self.conn.execute(
            "UPDATE posts SET comment = ? WHERE post_id = ?", (comment, post_id)
        )
        self.conn.commit()
        utils.log(f"Updated comment for post {post_id}", level="info")

    def delete_post(self, post_id):
        self.conn.execute("DELETE FROM posts WHERE post_id = ?", (post_id,))
        self.conn.commit()

    def get_available_actions(self, user, action_type):
        # retrieve actions (of type "challenge", etc.) which the user has not yet completed
        # return as list of dicts

        # get user's team
        team_id = None
        team = self.get_team_for_user(user["pax_id"])

        if team:
            team_id = team["team_id"]

        # get all the actions completed by `team_id` in the table `posts`
        completed_actions = self.get_table_as_df("posts")

        completed_actions = completed_actions[
            completed_actions["action_type"] == action_type
        ]
        completed_actions = completed_actions[completed_actions["team_id"] == team_id]
        completed_actions = completed_actions["action_name"].unique()

        # get all the actions of type `challenge_type` from the table `actions`
        if action_type == "challenge":
            available_actions = self.get_table_as_df("challenges")
        elif action_type == "checkpoint":
            available_actions = self.get_table_as_df("checkpoints")

        available_actions = available_actions[
            ~available_actions["name"].isin(completed_actions)
        ]

        # convert df to list with dicts
        available_actions = available_actions.to_dict("records")

        return available_actions

    def get_teams(self):
        # retrieve all teams from the database, return as pandas df
        return pd.read_sql_query("SELECT * FROM teams", self.conn)

    def get_available_participants(self, pax_id, team):
        all_paxes = self.get_participants(
            fetch_teams=True, sort_by_name=True, include_non_registered=True
        )

        if all_paxes.empty:
            return []

        # remove the current user (they are not available for themselves)
        all_paxes = all_paxes[all_paxes["id"] != pax_id]

        if team:
            # find a teammate for the current user
            teammate = team["member1"] if team["member1"] != pax_id else team["member2"]
        else:
            teammate = None

        # no team or teammate
        available_paxes = all_paxes[all_paxes["team_id"].isnull()]

        # prepend the "nobody option"
        available_paxes = pd.concat(
            [
                pd.DataFrame(
                    {
                        "id": ["-1"],
                        "name": ["(bez parťáka)"],
                    }
                ),
                available_paxes,
            ],
            ignore_index=True,
        )

        if teammate:
            # teammate is not in the list because they are already in a team, but we want to show them as available
            teammate_row = all_paxes[all_paxes["id"] == teammate]
            available_paxes = pd.concat(
                [teammate_row, available_paxes], ignore_index=True
            )

        return available_paxes

    def add_or_update_team(
        self,
        team_name,
        team_motto,
        team_web,
        team_photo,
        first_member,
        second_member,
        current_team=None,
    ):
        # if team is already in the database, get its id
        if current_team:
            team_id = current_team["team_id"]
        else:
            # add team to the database
            team_id = utils.generate_uuid()

        if str(second_member) == "-1":
            second_member = None

        photo_path = None
        if team_photo:
            photo_dir = os.path.join(self.top_dir, "teams", slugify(team_name))

            photo_content, photo_name = utils.postprocess_uploaded_photo(team_photo)

            photo_path = os.path.join(photo_dir, photo_name)
            self.write_file(filepath=photo_path, content=photo_content)
        else:
            # if photo already exists in the database, keep it
            if current_team:
                photo_path = current_team["team_photo"]

        if not current_team:
            self.conn.execute(
                f"INSERT INTO teams (team_id, team_name, team_motto, team_web, team_photo, member1, member2, is_top_x) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    team_id,
                    team_name,
                    team_motto,
                    team_web,
                    photo_path,
                    first_member,
                    second_member,
                    0,
                ),
            )
            self.conn.commit()
            utils.log(f"Added team {team_name}", level="success")
        else:
            # only update new values, keep the existing
            self.conn.execute(
                f"UPDATE teams SET team_name = ?, team_motto = ?, team_web = ?, team_photo = ?, member1 = ?, member2 = ? WHERE team_id = ?",
                (
                    team_name,
                    team_motto,
                    team_web,
                    photo_path,
                    first_member,
                    second_member,
                    team_id,
                ),
            )
            self.conn.commit()
            utils.log(f"Updated team {team_name}", level="info")

    def create_tables(self):
        self.conn.execute(
            """CREATE TABLE if not exists participants (
                id text not null unique,
                email text not null unique,
                name_web text not null,
                bio text,
                emergency_contact text,
                photo text,
                primary key(id)       
            );"""
        )
        self.conn.execute(
            """CREATE TABLE if not exists teams (
                team_id text not null unique,
                team_name text not null,
                member1 text not null,
                member2 text,
                member3 text,
                team_motto text,
                team_web text,
                team_photo text,
                is_top_x integer default 0,
                location_visibility integer default 1,
                location_color text,
                location_icon_color text,
                location_icon text,
                award text,
                primary key(team_id)   
            );"""
        )
        self.conn.execute(
            """CREATE TABLE if not exists posts (
                post_id text not null unique,
                pax_id text not null,
                team_id text,
                action_type text not null,
                action_name text not null,
                comment text,
                created text not null,
                files text,
                primary key(post_id),
                CONSTRAINT unique_post_entry UNIQUE (action_name, action_type, team_id)
            );"""
        )
        self.conn.execute(
            """CREATE TABLE if not exists locations (
                username text not null,
                team_id text not null,
                comment text,
                longitude float not null,
                latitude float not null,
                accuracy text,
                altitude text,
                altitude_accuracy text,
                heading text,
                speed text,
                address text,
                date text not null
            );"""
        )
        self.conn.execute(
            """CREATE TABLE if not exists challenges (
                name text not null unique,
                description text not null,
                category text not null,
                points int not null,
                primary key(name)       
            );"""
        )
        self.conn.execute(
            """CREATE TABLE if not exists checkpoints (
                name text not null unique,
                description text not null,
                points int not null,
                latitude float,
                longitude float,
                challenge text,
                primary key(name)       
            );"""
        )
        self.conn.execute(
            """CREATE TABLE if not exists notifications (
                text text not null,
                type text
            );"""
        )

    def get_address(self, latitude, longitude):
        try:
            locname = self.geoloc.reverse(f"{latitude}, {longitude}")
            address = locname.address
        except:
            address = None

        return address

    def parse_position(self, position):
        # position is a string
        # first, let's try to parse GPS coordinates
        position = self.geoloc.geocode(position)

        if position:
            return position

        return None

    def save_location(
        self,
        user,
        comment,
        longitude,
        latitude,
        accuracy,
        altitude,
        altitude_accuracy,
        heading,
        speed,
        address,
        date,
    ):
        team = self.get_team_for_user(user["pax_id"])
        username = user["username"]
        team_id = str(team["team_id"])

        self.conn.execute(
            f"INSERT INTO locations (username, team_id, comment, longitude, latitude, accuracy, altitude, altitude_accuracy, heading, speed, address, date) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                username,
                team_id,
                comment,
                longitude,
                latitude,
                accuracy,
                altitude,
                altitude_accuracy,
                heading,
                speed,
                address,
                date,
            ),
        )
        self.conn.commit()
        # utils.log(f"Saved location {latitude}, {longitude} for {username}", level="success")

    def save_location_options(
        self, team, location_color, location_icon_color, location_icon
    ):
        team_id = str(team["team_id"])

        self.conn.execute(
            f"UPDATE teams SET location_color='{location_color}', location_icon_color='{location_icon_color}', location_icon='{location_icon}' WHERE team_id='{team_id}'"
        )
        self.conn.commit()
        utils.log(f"Updated location options for {team['team_name']}", level="info")

    def get_last_location(_self, team, for_datetime=None):
        team_id = team["team_id"]

        if not for_datetime:
            for_datetime = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # df = pd.read_sql_query(
        #     f"SELECT * FROM locations WHERE team_id='{team_id}' AND team_id='{team_id}' ORDER BY date DESC LIMIT 1",
        #     _self.conn,
        # )

        # select the last location for the given datetime
        df = pd.read_sql_query(
            f"SELECT * FROM locations WHERE team_id='{team_id}' AND date <= '{for_datetime}' ORDER BY date DESC LIMIT 1",
            _self.conn,
        )

        if df.empty:
            return None

        return df.to_dict("records")[0]

    def get_locations_as_gpx(_self, team):
        team_id = team["team_id"]

        df = pd.read_sql_query(
            f"SELECT * FROM locations WHERE team_id='{team_id}'",
            _self.conn,
        )
        if df.empty:
            return None

        gpx = GPX()

        xc_year = _self.event["year"]
        team_name = team["team_name"]
        route = GPXRoute(name=f"{team_name} – Letní X-Challenge {xc_year}")
        gpx.routes.append(route)

        for i, location in df.iterrows():
            gpx_routepoint = GPXRoutePoint(
                latitude=location["latitude"],
                longitude=location["longitude"],
            )
            route.points.append(gpx_routepoint)

            date = dateutil.parser.parse(location["date"])
            date_text = date.strftime("%d.%m. %H:%M")

            waypoint = GPXWaypoint(
                latitude=location["latitude"],
                longitude=location["longitude"],
                time=date,
                name=f"{date_text}",
                description=location["comment"],
            )
            gpx.waypoints.append(waypoint)

        return gpx.to_xml()

    def get_last_locations(_self, for_datetime=None):
        # get last locations of all teams
        teams = _self.get_table_as_df("teams")
        last_locations = []

        for _, team in teams.iterrows():
            # get last location of the team
            last_location = _self.get_last_location(team, for_datetime=for_datetime)

            if last_location is None:
                continue

            if not _self.is_team_visible(team):
                continue

            last_locations.append(last_location)

        if not last_locations:
            return None

        # create dataframe from the list of locations
        last_locations = pd.DataFrame(last_locations)

        return last_locations

    def delete_location(self, location):
        username = location["username"]
        date = location["date"]

        self.conn.execute(
            f"DELETE FROM locations WHERE username='{username}' AND date='{date}'"
        )
        self.conn.commit()

        utils.log(f"Deleted location {username} {date}", level="info")

    def is_team_visible(self, team):
        visibility = team["location_visibility"]

        # by mistake some records are NULL and not 1 by default
        if visibility is None:
            visibility = 1

        return bool(visibility)

    def is_top_x(self, team):
        team_id = team["team_id"]

        df = pd.read_sql_query(
            f"SELECT * FROM teams WHERE team_id='{team_id}'",
            self.conn,
        )
        is_top_x = df.to_dict("records")[0]["is_top_x"]

        if is_top_x is None:
            is_top_x = 0

        return bool(is_top_x)

    def get_fa_icons(self):
        return self.fa_icons

    def get_team_link(self, team):
        team_id = team["team_id"]
        team_name = team["team_name"]
        is_top_x = bool(int(team["is_top_x"]))

        if is_top_x:
            # there is no other good way how to incorporate a static image into html (without st.image())
            data_url = self.get_static_image_base64("topx.png")

            top_x_badge = f"<img src='data:image/png;base64,{data_url}' style='margin-top: -5px; margin-left: 5px'>"
            return f"<a href='/Týmy?team_id={team_id}&event_id={self.event['id']}' target='_self' class='app-link' margin-top: -10px;'>{team_name}</a> {top_x_badge}"
        else:
            return f"<a href='/Týmy?team_id={team_id}&event_id={self.event['id']}' target='_self' class='app-link' margin-top: -10px;'>{team_name}</a>"

    def toggle_team_visibility(self, team):
        team_id = team["team_id"]

        df = pd.read_sql_query(
            f"SELECT * FROM teams WHERE team_id='{team_id}'",
            self.conn,
        )

        visibility = df.to_dict("records")[0]["location_visibility"]

        if visibility is None:
            visibility = 1

        visibility = 1 - visibility

        self.conn.execute(
            f"UPDATE teams SET location_visibility={visibility} WHERE team_id='{team_id}'",
        )
        self.conn.commit()

        return visibility

    def find_files_2022(self, action_type, action_name, team_id):
        files = []
        mt = mimetypes.MimeTypes()

        try:
            team_name = self.get_team_by_id(team_id)

            if not team_name:
                utils.log(f"Team {team_id} not found", level="warning")
                return files
            team_name = team_name["team_name"]

            path = os.path.join(
                "files", "2022", action_type, slugify(action_name), slugify(team_name)
            )

            # find all files in the directory
            for file in os.listdir(path):
                if file.endswith(".txt") or os.path.isdir(os.path.join(path, file)):
                    continue

                file_path = os.path.join(path, file)
                file_type = mt.guess_type(path)[0]

                if not file_type:
                    # guess from the extension
                    extension = file.split(".")[-1]
                    file_type = (
                        f"video/{extension}"
                        if extension.lower() in ["mp4", "mov", "avi"]
                        else f"image/{extension}"
                    )

                files.append({"path": file_path, "type": file_type})
        except FileNotFoundError:
            pass

        return files

    def insert_data_2022(self):
        with open("files/2022/prihlasky.csv") as f:
            reader = csv.DictReader(f, delimiter=",")
            for i, row in enumerate(reader):
                # note that we use here member names as ids
                self.conn.execute(
                    """INSERT OR IGNORE INTO teams
                    (team_id, team_name, member1, member2)
                    VALUES
                    (?, ?, ?, ?);
                    """,
                    (
                        f"2022_team_{i + 1}",
                        row["Název týmu"],
                        "2022_" + slugify(row["Člen #1: Jméno a příjmení"]),
                        "2022_" + slugify(row["Člen #2: Jméno a příjmení"]),
                    ),
                )
                self.conn.execute(
                    """INSERT OR IGNORE INTO participants
                    (id, email, name_web)
                    VALUES
                    (?, ?, ?);
                    """,
                    (
                        "2022_" + slugify(row["Člen #1: Jméno a příjmení"]),
                        utils.generate_uuid() + "@xc-test.cz",
                        row["Člen #1: Jméno a příjmení"],
                    ),
                )
                self.conn.execute(
                    """INSERT OR IGNORE INTO participants
                    (id, email, name_web)
                    VALUES
                    (?, ?, ?);
                    """,
                    (
                        "2022_" + slugify(row["Člen #2: Jméno a příjmení"]),
                        utils.generate_uuid() + "@xc-test.cz",
                        row["Člen #2: Jméno a příjmení"],
                    ),
                )
            self.conn.commit()

        with open("files/2022/odpovedi.csv") as f:
            reader = csv.DictReader(f, delimiter=",")
            for i, row in enumerate(reader):
                username = "xc-bot"
                team_id = "2022_team_" + row["ID týmu"]

                # format from %d/%m/%Y %H:%M:%S to %Y-%m-%d %H:%M:%S")
                timestamp = row["Timestamp"]
                timestamp = datetime.strptime(timestamp, "%d/%m/%Y %H:%M:%S").strftime(
                    "%Y-%m-%d %H:%M:%S"
                )

                action_type_dict = {
                    "⭐ splněnou výzvu": "challenge",
                    "📍 splněný checkpoint": "checkpoint",
                    "✍️ příspěvek": "story",
                }
                action_type = action_type_dict[row["Chci přidat..."]]

                if action_type == "challenge":
                    action_name = row["Výzva"]
                    comment = row["Komentář - Výzva"]
                elif action_type == "checkpoint":
                    action_name = row["Checkpoint"]
                    comment = row["Komentář - Checkpoint"]
                elif action_type == "story":
                    action_name = row["Nadpis"]
                    comment = row["Text"]

                files = self.find_files_2022(action_type, action_name, team_id)
                files = json.dumps(files)

                self.conn.execute(
                    """INSERT OR IGNORE INTO posts
                    (post_id, pax_id, team_id, action_type, action_name, comment, created, files)
                    VALUES
                    (?, ?, ?, ?, ?, ?, ?, ?);
                    """,
                    (
                        "2022_" + utils.generate_uuid(),
                        username,
                        team_id,
                        action_type,
                        action_name,
                        comment,
                        timestamp,
                        files,
                    ),
                )
            self.conn.commit()

        with open("files/2022/challenges.csv") as f:
            reader = csv.DictReader(f, delimiter=",")
            for i, row in enumerate(reader):
                self.conn.execute(
                    """INSERT OR IGNORE INTO challenges
                    (name, category, description, points)
                    VALUES
                    (?, ?, ?, ?);
                    """,
                    (
                        row["název"],
                        row["kategorie"],
                        row["popis"],
                        row["počet bodů"],
                    ),
                )
            self.conn.commit()

        with open("files/2022/checkpoints.csv") as f:
            reader = csv.DictReader(f, delimiter=",")
            for i, row in enumerate(reader):
                gps = row["gps"]

                try:
                    # remove all letters
                    gps = re.sub("[a-zA-Z]", "", gps)
                    gps = gps.split(",")[:2]

                    lat = float(gps[0].strip())
                    lon = float(gps[1].strip())
                except:
                    utils.log(f"Cannot convert {gps}", level="warning")
                    gps = None

                self.conn.execute(
                    """INSERT OR IGNORE INTO checkpoints
                    (name, description, points, challenge, latitude, longitude)
                    VALUES
                    (?, ?, ?, ?, ?, ?);
                    """,
                    (
                        row["název"],
                        row["popis"],
                        row["počet bodů"],
                        row["výzva (dobrovolná)"],
                        lat,
                        lon,
                    ),
                )
            self.conn.commit()


if __name__ == "__main__":
    # read arguments
    parser = argparse.ArgumentParser()
    parser.add_argument("-p", "--load_from_wc_product", type=int)
    parser.add_argument("-f", "--load_from_local_file", type=str)
    parser.add_argument("--fill_addresses", action="store_true")
    parser.add_argument("--insert_data_2022", action="store_true")
    parser.add_argument("--reslugify", action="store_true")
    # parser.add_argument("--export_static_website", action="store_true")

    args = parser.parse_args()

    print(args)
    print("Creating database...")

    if args.insert_data_2022:
        db = Database(event_id="2022")
        db.create_tables()
        db.insert_data_2022()
        exit()

    db = Database()
    db.create_tables()

    if args.load_from_wc_product:
        print("Fetching participants from Woocommerce...")
        db.wc_fetch_participants(product_id=args.load_from_wc_product)
    elif args.load_from_local_file:
        print("Loading users from file...")
        with open(args.load_from_local_file) as f:
            wc_participants = json.load(f)
            db.add_participants(wc_participants)

    # elif args.export_static_website:
    #     print("Exporting static website...")
    #     db = Database(event_id="2022")
    #     db.export_static_website("exported_website", "2022")

    elif args.fill_addresses:
        print("Filling addresses...")

        # importing modules
        from geopy.geocoders import Nominatim

        # calling the nominatim tool
        geoLoc = Nominatim(user_agent="GetLoc")

        for i, row in db.get_table_as_df("locations").iterrows():
            print(row)
            if row["address"] == None:
                print(dict(row))
                location = geoLoc.reverse(f"{row['latitude']}, {row['longitude']}")
                db.conn.execute(
                    """UPDATE locations
                    SET address = ?
                    WHERE team_id = ? AND date = ?;
                    """,
                    (location.address, row["team_id"], row["date"]),
                )
                db.conn.commit()
                print(location.address)
    elif args.reslugify:
        # hotfix - we forgot to slugify folders
        for i, row in db.get_table_as_df("posts").iterrows():
            challenge_name = row["action_name"]
            challenge_slug = slugify(challenge_name)
            files = json.loads(row["files"])
            new_files = copy.deepcopy(files)

            if not files:
                continue

            for i, file in enumerate(files):
                path = file["path"]
                path_parts = path.split("/")
                path_parts[3] = challenge_slug
                new_path = "/".join(path_parts)
                new_files[i]["path"] = new_path

                if path != new_path:
                    print(len(files))
                    print(path, "->", new_path)
                    # save files on the new path
                    db.write_file(new_path, db.read_file(path))
                    db.delete_file(path)

            # update `files` as new_files in db
            db.conn.execute(
                """UPDATE posts
                SET files = ?
                WHERE post_id = ?;
                """,
                (json.dumps(new_files), row["post_id"]),
            )
            db.conn.commit()
