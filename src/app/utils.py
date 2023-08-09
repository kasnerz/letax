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
    hours = diff.seconds // 3600

    if diff.days > 0:
        return f"před {diff.days} dny"
    # hours
    elif hours > 0:
        return f"před {hours} hodinami"

    return "před méně než hodinou"


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


def get_fa_icons():
    # fmt: off
    return ["500px", "address-book", "address-book-o", "address-card", "address-card-o", "adjust", "adn", "align-center", "align-justify", "align-left", "align-right", "amazon", "ambulance", "american-sign-language-interpreting", "anchor", "android", "angellist", "angle-double-down", "angle-double-left", "angle-double-right", "angle-double-up", "angle-down", "angle-left", "angle-right", "angle-up", "apple", "archive", "area-chart", "arrow-circle-down", "arrow-circle-left", "arrow-circle-o-down", "arrow-circle-o-left", "arrow-circle-o-right", "arrow-circle-o-up", "arrow-circle-right", "arrow-circle-up", "arrow-down", "arrow-left", "arrow-right", "arrow-up", "arrows", "arrows-alt", "arrows-h", "arrows-v", "asl-interpreting", "assistive-listening-systems", "asterisk", "at", "audio-description", "automobile", "backward", "balance-scale", "ban", "bandcamp", "bank", "bar-chart", "bar-chart-o", "barcode", "bars", "bath", "bathtub", "battery", "battery-0", "battery-1", "battery-2", "battery-3", "battery-4", "battery-empty", "battery-full", "battery-half", "battery-quarter", "battery-three-quarters", "bed", "beer", "behance", "behance-square", "bell", "bell-o", "bell-slash", "bell-slash-o", "bicycle", "binoculars", "birthday-cake", "bitbucket", "bitbucket-square", "bitcoin", "black-tie", "blind", "bluetooth", "bluetooth-b", "bold", "bolt", "bomb", "book", "bookmark", "bookmark-o", "braille", "briefcase", "btc", "bug", "building", "building-o", "bullhorn", "bullseye", "bus", "buysellads", "cab", "calculator", "calendar", "calendar-check-o", "calendar-minus-o", "calendar-o", "calendar-plus-o", "calendar-times-o", "camera", "camera-retro", "car", "caret-down", "caret-left", "caret-right", "caret-square-o-down", "caret-square-o-left", "caret-square-o-right", "caret-square-o-up", "caret-up", "cart-arrow-down", "cart-plus", "cc", "cc-amex", "cc-diners-club", "cc-discover", "cc-jcb", "cc-mastercard", "cc-paypal", "cc-stripe", "cc-visa", "certificate", "chain", "chain-broken", "check", "check-circle", "check-circle-o", "check-square", "check-square-o", "chevron-circle-down", "chevron-circle-left", "chevron-circle-right", "chevron-circle-up", "chevron-down", "chevron-left", "chevron-right", "chevron-up", "child", "chrome", "circle", "circle-o", "circle-o-notch", "circle-thin", "clipboard", "clock-o", "clone", "close", "cloud", "cloud-download", "cloud-upload", "cny", "code", "code-fork", "codepen", "codiepie", "coffee", "cog", "cogs", "columns", "comment", "comment-o", "commenting", "commenting-o", "comments", "comments-o", "compass", "compress", "connectdevelop", "contao", "copy", "copyright", "creative-commons", "credit-card", "credit-card-alt", "crop", "crosshairs", "css3", "cube", "cubes", "cut", "cutlery", "dashboard", "dashcube", "database", "deaf", "deafness", "dedent", "delicious", "desktop", "deviantart", "diamond", "digg", "dollar", "dot-circle-o", "download", "dribbble", "drivers-license", "drivers-license-o", "dropbox", "drupal", "edge", "edit", "eercast", "eject", "ellipsis-h", "ellipsis-v", "empire", "envelope", "envelope-o", "envelope-open", "envelope-open-o", "envelope-square", "envira", "eraser", "etsy", "eur", "euro", "exchange", "exclamation", "exclamation-circle", "exclamation-triangle", "expand", "expeditedssl", "external-link", "external-link-square", "eye", "eye-slash", "eyedropper", "fa", "facebook", "facebook-f", "facebook-official", "facebook-square", "fast-backward", "fast-forward", "fax", "feed", "female", "fighter-jet", "file", "file-archive-o", "file-audio-o", "file-code-o", "file-excel-o", "file-image-o", "file-movie-o", "file-o", "file-pdf-o", "file-photo-o", "file-picture-o", "file-powerpoint-o", "file-sound-o", "file-text", "file-text-o", "file-video-o", "file-word-o", "file-zip-o", "files-o", "film", "filter", "fire", "fire-extinguisher", "firefox", "first-order", "flag", "flag-checkered", "flag-o", "flash", "flask", "flickr", "floppy-o", "folder", "folder-o", "folder-open", "folder-open-o", "font", "font-awesome", "fonticons", "fort-awesome", "forumbee", "forward", "foursquare", "free-code-camp", "frown-o", "futbol-o", "gamepad", "gavel", "gbp", "ge", "gear", "gears", "genderless", "get-pocket", "gg", "gg-circle", "gift", "git", "git-square", "github", "github-alt", "github-square", "gitlab", "gittip", "glass", "glide", "glide-g", "globe", "google", "google-plus", "google-plus-circle", "google-plus-official", "google-plus-square", "google-wallet", "graduation-cap", "gratipay", "grav", "group", "h-square", "hacker-news", "hand-grab-o", "hand-lizard-o", "hand-o-down", "hand-o-left", "hand-o-right", "hand-o-up", "hand-paper-o", "hand-peace-o", "hand-pointer-o", "hand-rock-o", "hand-scissors-o", "hand-spock-o", "hand-stop-o", "handshake-o", "hard-of-hearing", "hashtag", "hdd-o", "header", "headphones", "heart", "heart-o", "heartbeat", "history", "home", "hospital-o", "hotel", "hourglass", "hourglass-1", "hourglass-2", "hourglass-3", "hourglass-end", "hourglass-half", "hourglass-o", "hourglass-start", "houzz", "html5", "i-cursor", "id-badge", "id-card", "id-card-o", "ils", "image", "imdb", "inbox", "indent", "industry", "info", "info-circle", "inr", "instagram", "institution", "internet-explorer", "intersex", "ioxhost", "italic", "joomla", "jpy", "jsfiddle", "key", "keyboard-o", "krw", "language", "laptop", "lastfm", "lastfm-square", "leaf", "leanpub", "legal", "lemon-o", "level-down", "level-up", "life-bouy", "life-buoy", "life-ring", "life-saver", "lightbulb-o", "line-chart", "link", "linkedin", "linkedin-square", "linode", "linux", "list", "list-alt", "list-ol", "list-ul", "location-arrow", "lock", "long-arrow-down", "long-arrow-left", "long-arrow-right", "long-arrow-up", "low-vision", "magic", "magnet", "mail-forward", "mail-reply", "mail-reply-all", "male", "map", "map-marker", "map-o", "map-pin", "map-signs", "mars", "mars-double", "mars-stroke", "mars-stroke-h", "mars-stroke-v", "maxcdn", "meanpath", "medium", "medkit", "meetup", "meh-o", "mercury", "microchip", "microphone", "microphone-slash", "minus", "minus-circle", "minus-square", "minus-square-o", "mixcloud", "mobile", "mobile-phone", "modx", "money", "moon-o", "mortar-board", "motorcycle", "mouse-pointer", "music", "navicon", "neuter", "newspaper-o", "object-group", "object-ungroup", "odnoklassniki", "odnoklassniki-square", "opencart", "openid", "opera", "optin-monster", "outdent", "pagelines", "paint-brush", "paper-plane", "paper-plane-o", "paperclip", "paragraph", "paste", "pause", "pause-circle", "pause-circle-o", "paw", "paypal", "pencil", "pencil-square", "pencil-square-o", "percent", "phone", "phone-square", "photo", "picture-o", "pie-chart", "pied-piper", "pied-piper-alt", "pied-piper-pp", "pinterest", "pinterest-p", "pinterest-square", "plane", "play", "play-circle", "play-circle-o", "plug", "plus", "plus-circle", "plus-square", "plus-square-o", "podcast", "power-off", "print", "product-hunt", "puzzle-piece", "qq", "qrcode", "question", "question-circle", "question-circle-o", "quora", "quote-left", "quote-right", "ra", "random", "ravelry", "rebel", "recycle", "reddit", "reddit-alien", "reddit-square", "refresh", "registered", "remove", "renren", "reorder", "repeat", "reply", "reply-all", "resistance", "retweet", "rmb", "road", "rocket", "rotate-left", "rotate-right", "rouble", "rss", "rss-square", "rub", "ruble", "rupee", "s15", "safari", "save", "scissors", "scribd", "search", "search-minus", "search-plus", "sellsy", "send", "send-o", "server", "share", "share-alt", "share-alt-square", "share-square", "share-square-o", "shekel", "sheqel", "shield", "ship", "shirtsinbulk", "shopping-bag", "shopping-basket", "shopping-cart", "shower", "sign-in", "sign-language", "sign-out", "signal", "signing", "simplybuilt", "sitemap", "skyatlas", "skype", "slack", "sliders", "slideshare", "smile-o", "snapchat", "snapchat-ghost", "snapchat-square", "snowflake-o", "soccer-ball-o", "sort", "sort-alpha-asc", "sort-alpha-desc", "sort-amount-asc", "sort-amount-desc", "sort-asc", "sort-desc", "sort-down", "sort-numeric-asc", "sort-numeric-desc", "sort-up", "soundcloud", "space-shuttle", "spinner", "spoon", "spotify", "square", "square-o", "stack-exchange", "stack-overflow", "star", "star-half", "star-half-empty", "star-half-full", "star-half-o", "star-o", "steam", "steam-square", "step-backward", "step-forward", "stethoscope", "sticky-note", "sticky-note-o", "stop", "stop-circle", "stop-circle-o", "street-view", "strikethrough", "stumbleupon", "stumbleupon-circle", "subscript", "subway", "suitcase", "sun-o", "superpowers", "superscript", "support", "table", "tablet", "tachometer", "tag", "tags", "tasks", "taxi", "telegram", "television", "tencent-weibo", "terminal", "text-height", "text-width", "th", "th-large", "th-list", "themeisle", "thermometer", "thermometer-0", "thermometer-1", "thermometer-2", "thermometer-3", "thermometer-4", "thermometer-empty", "thermometer-full", "thermometer-half", "thermometer-quarter", "thermometer-three-quarters", "thumb-tack", "thumbs-down", "thumbs-o-down", "thumbs-o-up", "thumbs-up", "ticket", "times", "times-circle", "times-circle-o", "times-rectangle", "times-rectangle-o", "tint", "toggle-down", "toggle-left", "toggle-off", "toggle-on", "toggle-right", "toggle-up", "trademark", "train", "transgender", "transgender-alt", "trash", "trash-o", "tree", "trello", "tripadvisor", "trophy", "truck", "try", "tty", "tumblr", "tumblr-square", "turkish-lira", "tv", "twitch", "twitter", "twitter-square", "umbrella", "underline", "undo", "universal-access", "university", "unlink", "unlock", "unlock-alt", "unsorted", "upload", "usb", "usd", "user", "user-circle", "user-circle-o", "user-md", "user-o", "user-plus", "user-secret", "user-times", "users", "vcard", "vcard-o", "venus", "venus-double", "venus-mars", "viacoin", "viadeo", "viadeo-square", "video-camera", "vimeo", "vimeo-square", "vine", "vk", "volume-control-phone", "volume-down", "volume-off", "volume-up", "warning", "wechat", "weibo", "weixin", "whatsapp", "wheelchair", "wheelchair-alt", "wifi", "wikipedia-w", "window-close", "window-close-o", "window-maximize", "window-minimize", "window-restore", "windows", "won", "wordpress", "wpbeginner", "wpexplorer", "wpforms", "wrench", "xing", "xing-square", "y-combinator", "y-combinator-square", "yahoo", "yc", "yc-square", "yelp", "yen", "yoast", "youtube", "youtube-play", "youtube-square"]
    # fmt: on


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
