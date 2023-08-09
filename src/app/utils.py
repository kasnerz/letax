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
from streamlit_extras import app_logo
import subprocess
import ffmpeg
from datetime import datetime, timedelta

TTL = 600


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
        print(f"Logging to mailserver...")
        server.login(sender_email, password)
        print(f"Sending e-mail from {sender_email} to {address}")
        server.sendmail(sender_email, address, message.as_string())
        print("E-mail sent")

    return True


def escape_html(s):
    s = s.replace("<", "&lt;").replace(">", "&gt;")
    s = s.replace("\n", "<br>")

    return s


def ago(t):
    t = pd.to_datetime(t)
    diff = datetime.now() - t

    if diff.days > 0:
        return f"před {diff.days} dny"

    # hours
    elif diff.seconds > 3600:
        return f"před {diff.hours} hodinami"

    # minutes
    elif diff.seconds > 60:
        return f"před {diff.minutes} minutami"

    return "právě teď"


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

    # TODO resize?

    photo_content = open(photo_path, "rb").read()
    os.remove(photo_path)

    return photo_content, photo_name


def postprocess_ffmpeg(input_file, output_file):
    # use ffmpeg-python to efficiently convert the video to a reasonable sized-file
    try:
        input_stream = ffmpeg.input(input_file)
        output_stream = ffmpeg.output(input_stream, output_file, crf=26, preset="fast")
        ffmpeg.run(output_stream)
        print(f"Video successfully postprocessed and saved as {output_file}")
    except ffmpeg.Error as e:
        print(f"An error occurred: {e}")


def postprocess_uploaded_video(video):
    # video is a Streamlit uploaded object
    # generate a unique filename

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
    st.write(f"Zpracovávám video {original_video_path}, může to chvíli trvat, prosím vydrž...")

    # TODO write about ffmpeg as a dependency
    postprocess_ffmpeg(original_video_path, video_path)
    os.remove(original_video_path)

    video_content = open(video_path, "rb").read()
    video_name = f"{video_uuid}_pp.mp4"

    return video_content, video_name


@st.cache_resource(ttl=TTL)
def resize_image(img, max_width=None, crop_ratio=None, circle=False):
    # timeit
    start = time.time()

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

    end = time.time()
    # print(f"resize_image took {end - start} seconds")

    return img


def style_sidebar():
    st.markdown(
        """
    <style>
    div[data-testid='stSidebarNav'] ul {max-height:none}</style>
    """,
        unsafe_allow_html=True,
    )

    app_logo.add_logo("static/letax.png", height=40)


def clear_cache():
    st.cache_resource.clear()
    st.cache_data.clear()
