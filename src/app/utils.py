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
    print(f"resize_image took {end - start} seconds")

    return img


def style_sidebar():
    st.sidebar.warning("Aplikace běží v testovacím režimu!")

    st.markdown(
        """
    <style>
    div[data-testid='stSidebarNav'] ul {max-height:none}</style>
    """,
        unsafe_allow_html=True,
    )

    app_logo.add_logo("static/logo_small.png", height=60)
