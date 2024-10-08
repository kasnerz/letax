#!/usr/bin/env python3
import time
import yaml
import os
import uuid
import streamlit as st
from PIL import Image, ImageOps, ImageDraw
import pandas as pd
import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import subprocess
import ffmpeg
from datetime import datetime, timedelta
import pytz
import base64
import psutil
import gc
from streamlit_javascript import st_javascript
from ftplib import FTP
from pathlib import Path
from unidecode import unidecode

TTL = 600


def log(m, level="info"):
    # We don't want to use the logging module since it's used by Streamlit
    current_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())

    if level == "info":
        print("{} - \033[96m{}\033[00m {}".format(current_time, level.upper(), m))
    elif level == "warning":
        print("{} - \033[93m{}\033[00m {}".format(current_time, level.upper(), m))
    elif level == "error":
        print("{} - \033[91m{}\033[00m {}".format(current_time, level.upper(), m))
    elif level == "debug":
        print("{} - \033[95m{}\033[00m {}".format(current_time, level.upper(), m))
    elif level == "success":
        print("{} - \033[92m{}\033[00m {}".format(current_time, level.upper(), m))
    else:
        print("{} - {} {}".format(current_time, level.upper(), m))

    # write to file
    with open("letax.log", "a") as f:
        f.write("{} - {} {}\n".format(current_time, level.upper(), m))


def generate_uuid():
    # generate a short unique uuid
    return str(uuid.uuid4())[:8]


def send_email(address, subject, content_html):
    port = 465  # For SSL
    smtp_server = st.secrets["email"]["smtp_server"]
    password = st.secrets["email"]["password"]
    sender_email = "letni@x-challenge.cz"

    # Create a secure SSL context
    context = ssl.create_default_context()

    message = MIMEMultipart("alternative")
    message["Subject"] = subject
    message["From"] = sender_email
    message["To"] = address

    # Turn these into plain/html MIMEText objects
    content_part = MIMEText(content_html, "html")
    message.attach(content_part)

    with smtplib.SMTP_SSL(smtp_server, port, context=context) as server:
        log(f"Logging to mailserver...", level="debug")
        server.login(sender_email, password)
        server.sendmail(sender_email, address, message.as_string())
        log(f"Sending e-mail from {sender_email} to {address}", level="info")

    return True


def escape_html(s):
    s = s.replace("<", "&lt;").replace(">", "&gt;")
    s = s.replace("\n", "<br>")

    return s


# @st.cache_data(ttl=600)
def ago(t):
    t = pd.to_datetime(t)
    # if off-set aware, remove the offset
    if t.tzinfo is not None and t.tzinfo.utcoffset(t) is not None:
        t = t.tz_convert(None)

    diff = datetime.now() - t
    hours = diff.seconds // 3600

    if diff.days > 1:
        return f"před {diff.days} dny"
    elif diff.days == 1:
        return "před 1 dnem"
    # hours
    elif hours > 1:
        return f"před {hours} hodinami"
    elif hours == 1:
        return "před hodinou"

    return "před méně než hodinou"


def get_readable_datetime(t_str):
    if "." in t_str:
        t_str = t_str.split(".")[0]

    return t_str[:-3]


def convert_datetime_server_to_prague(dt):
    delta = timedelta(hours=2)
    dt = dt + delta

    return dt


def convert_datetime_prague_to_server(dt):
    delta = timedelta(hours=-2)
    dt = dt + delta

    return dt


def heic_to_jpg(input_file, output_file):
    try:
        subprocess.run(["heif-convert", input_file, output_file], check=True)
        # TODO add libimage-exiftool-perl as a dependency
        subprocess.run(["exiftool", "-n", "-Orientation=1", output_file], check=True)
    except subprocess.CalledProcessError:
        raise Exception("Failed to convert HEIC to JPG. Is heif-convert installed?")


def postprocess_uploaded_photo(photo):
    # photo is a Streamlit uploaded object
    # generate a unique filename
    photo_uuid = generate_uuid()

    # original suffix
    photo_suffix = os.path.splitext(photo.name)[1].lower()

    # generate a unique filename
    photo_name = f"{photo_uuid}{photo_suffix}"
    photo_path = f"/tmp/{photo_name}"

    # save as a temporary file
    with open(photo_path, "wb") as f:
        f.write(photo.read())

    # if the photo is a HEIC, convert it to JPG
    if photo.type in ["image/heic", "image/heif"]:
        original_photo_path = photo_path
        photo_path = f"/tmp/{photo_uuid}.jpg"

        # TODO write about libheif as a dependency
        heic_to_jpg(original_photo_path, photo_path)

        os.remove(original_photo_path)
        photo_name = f"{photo_uuid}.jpg"

    photo_content = open(photo_path, "rb").read()
    os.remove(photo_path)

    return photo_content, photo_name


def postprocess_ffmpeg(input_file, output_file):
    # use ffmpeg-python to efficiently convert the video to a reasonable sized-file
    try:
        log(f"Postprocessing video {input_file}...", level="info")
        input_stream = ffmpeg.input(input_file)
        output_stream = ffmpeg.output(input_stream, output_file, crf=26, preset="fast")
        ffmpeg.run(output_stream, quiet=True)
        log(f"Video postprocessed and saved as {output_file}", level="success")
    except ffmpeg.Error as e:
        log(f"An error occurred: {e}", level="error")


def postprocess_uploaded_video(video):
    # video is a Streamlit uploaded object
    # generate a unique filename

    # cleanup: delete previous videos which are older than 1 hour
    for f in os.listdir("/tmp"):
        if f.endswith("_pp.mp4"):
            fpath = os.path.join("/tmp", f)
            if datetime.now() - datetime.fromtimestamp(
                os.path.getmtime(fpath)
            ) > timedelta(hours=1):
                os.remove(fpath)

    video_uuid = generate_uuid()

    # original suffix
    video_suffix = os.path.splitext(video.name)[1].lower()

    # generate a unique filename
    video_name = f"{video_uuid}{video_suffix}"
    video_path = f"/tmp/{video_name}"

    with open(video_path, "wb") as f:
        f.write(video.read())

    original_video_path = video_path
    video_path = f"/tmp/{video_uuid}_pp.mp4"
    st.write(
        f"Zpracovávám video {original_video_path}, může to chvíli trvat, prosím vydrž..."
    )

    # TODO write about ffmpeg as a dependency
    postprocess_ffmpeg(original_video_path, video_path)
    os.remove(original_video_path)

    video_content = open(video_path, "rb").read()
    video_name = f"{video_uuid}_pp.mp4"

    return video_content, video_name


@st.cache_resource(ttl=TTL)
def resize_image(img, max_width=None, max_height=None, crop_ratio=None, circle=False):
    # create a copy of img

    img = img.copy()

    if crop_ratio:
        crop_width, crop_height = map(int, crop_ratio.split(":"))

        width = img.size[0]
        height = img.size[1]
        aspect = width / float(height)
        ideal_aspect = crop_width / float(crop_height)

        if aspect > ideal_aspect:
            # Then crop the left and right edges:
            new_width = int(ideal_aspect * height)
            offset = (width - new_width) / 2
            resize = (offset, 0, width - offset, height)
        else:
            # ... crop the top and bottom:
            new_height = int(width / ideal_aspect)
            offset = (height - new_height) / 2
            resize = (0, offset, width, height - offset)

        img = img.crop(resize)

    if max_width and img.size[0] > max_width:
        img = img.resize((max_width, int(max_width * img.size[1] / img.size[0])))

    if max_height and img.size[1] > max_height:
        img = img.resize((int(max_height * img.size[0] / img.size[1]), max_height))

    # circle crop
    if circle:
        # Create a circular mask image
        mask = Image.new("L", img.size, 0)
        draw = ImageDraw.Draw(mask)
        draw.ellipse((0, 0) + img.size, fill=255)

        # Apply the mask to the image
        result = Image.new("RGBA", img.size)
        result.paste(img, mask=mask)
        img = result

    return img


def check_ram_limit():
    threshold_percentage = 85
    memory_info = psutil.virtual_memory()
    used_percentage = memory_info.percent

    if used_percentage > threshold_percentage:
        log(
            f"Used RAM: {used_percentage}%, clearing cache and calling garbage collector.",
            "debug",
        )
        clear_cache()
        gc.collect()


def get_active_event_id():
    # this needs to be outside db so that we can initialize the db for the first time
    current_dir = os.path.dirname(os.path.realpath(__file__))
    settings_path = os.path.join(current_dir, "settings.yaml")

    with open(settings_path) as f:
        settings = yaml.safe_load(f)

    active_event_id = settings.get("active_event_id")

    return active_event_id


def add_logo(logo_url: str, year: int, height: int = 120):
    # Adapted from https://arnaudmiribel.github.io/streamlit-extras/extras/app_logo/

    logo = f"url(data:image/png;base64,{base64.b64encode(Path(logo_url).read_bytes()).decode()})"

    st.html(
        f"""
        <style>
            [data-testid="stSidebarHeader"] {{
                background-image: {logo};
                background-repeat: no-repeat;
                padding-top: {height - 40}px;
                background-position: 25px 30px;
                padding-bottom: 70px;
            }}
            [data-testid="stSidebarHeader"]::before {{
                content: "Letní X-Challenge {year}";
                margin-left: 50px;
                font-size: 19px;
                font-weight: 700;
                font-family: "Source Sans Pro", sans-serif;
                position: relative;
                top: 31px;
            }}
        </style>
        """
    )


def page_wrapper():
    event = st.session_state.get("event")
    active_event = st.session_state.get("active_event")

    # currently the only way to detect streamlit theme
    bg_color = st_javascript(
        """window.getComputedStyle(window.parent.document.getElementsByClassName("stApp")[0]).getPropertyValue("background-color")"""
    )
    # bg_color is set to 0 until the page is loaded, we need to ignore it
    if bg_color:
        st.session_state.bg_color = bg_color
    if not hasattr(st.session_state, "bg_color"):
        st.session_state.bg_color = "rgb(255, 255, 255)"

    link_color = (
        "#002676" if st.session_state.bg_color == "rgb(255, 255, 255)" else "#6bb6fe"
    )

    st.markdown(
        """
    <style>
    div[data-testid='stSidebarNav'] ul {max-height:none}
    .app-link, a:link, a:visited {
        color: """
        + link_color
        + """ !important;
        text-decoration: none;
    }
    .table-display {
        width: 100%;
    }
    .table-display > thead > tr > th {
        text-align: left;
    }
    </style>
    """,
        unsafe_allow_html=True,
    )

    if event and active_event and event["year"] != active_event["year"]:
        st.markdown(
            """
        <style>
        div[data-testid='stSidebarNav'] {
            filter: grayscale(100%);
        }
        </style>
        """,
            unsafe_allow_html=True,
        )
        st.sidebar.info(f"Prohlížíš si ročník {event['year']}.")

        show_active_btn = st.sidebar.button(
            f"Zobrazit aktuální ročník {active_event['year']}"
        )

        if show_active_btn:
            st.session_state.event = None
            clear_cache()
            st.rerun()

    # st.logo("static/logo_icon.png")
    if not event:
        add_logo("static/logo_icon.png", year="", height=40)
    else:
        add_logo("static/logo_icon.png", year=event["year"], height=40)

    # it is useful to run it here since this gets called every time
    check_ram_limit()


def upload_to_ftp(local_dir, remote_dir):
    ftp = FTP(host=st.secrets["ftp"]["host"])
    ftp.login(user=st.secrets["ftp"]["login"], passwd=st.secrets["ftp"]["password"])

    # upload all the files from local_dir to remote_dir
    progress_text = "Nahrávám soubory"
    my_bar = st.progress(0, text=progress_text)

    all_files = list(os.walk(local_dir))
    for i, (root, dirs, files) in enumerate(all_files):
        for directory in dirs:
            remote_path = os.path.join(
                remote_dir, root.replace(local_dir, ""), directory
            )
            try:
                ftp.mkd(remote_path)
            except:
                pass

        for file in files:
            local_path = os.path.join(root, file)
            remote_path = os.path.join(remote_dir, root.replace(local_dir, ""), file)

            log(f"Uploading {local_path} to {remote_path}", "debug")

            with open(local_path, "rb") as f:
                ftp.storbinary(f"STOR {remote_path}", f)

            my_bar.progress(
                int(((i + 1) / len(all_files)) * 100),
                text=f"Nahrávám `{local_path}` do `{remote_path}`",
            )

    my_bar.progress(100)
    ftp.quit()


def get_event_id(params):
    if params.get("event_id"):
        return params["event_id"]

    elif st.session_state.get("event"):
        return st.session_state["event"]["year"]

    else:
        return get_active_event_id()

    return None


def normalize_username(username):
    username = unidecode(username.lower().strip().replace(" ", "_").replace("?", "_"))
    return username


def shorten_address(address):
    address_parts = address.split(",")

    if len(address_parts) > 3:
        address = ", ".join([address_parts[-3], address_parts[-1]])

    return address


def clear_cache():
    log("Clearing cache", "debug")
    st.cache_resource.clear()
    st.cache_data.clear()


def sort_challenges(challenges):
    # sort by name: letter case insensitive, interpunction before numbers (for day challenges on the top)

    if type(challenges) is list:
        sorting_fn = lambda x: x.lower().replace("[", "0")

        return sorted(challenges, key=lambda x: sorting_fn(x["name"]))

    # pd.DataFrame
    sorting_fn = lambda x: x.str.lower().str.replace("[", "0", regex=False)

    return challenges.sort_values(by="name", key=sorting_fn)


def convert_to_local_timezone(d):
    # d is a string in 2023-07-01 10:26:45 format, in GMT zone
    # convert to timezone UTC+2

    # convert to datetime object
    d = datetime.strptime(d, "%Y-%m-%d %H:%M:%S")

    # convert to UTC+2
    d = d + timedelta(hours=2)

    # convert to string
    d = d.strftime("%Y-%m-%d %H:%M:%S")

    return d
