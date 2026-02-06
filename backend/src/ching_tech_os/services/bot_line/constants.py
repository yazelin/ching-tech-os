"""Line Bot 常數定義"""

# 檔案類型對應的副檔名
FILE_TYPE_EXTENSIONS = {
    "image": ".jpg",
    "video": ".mp4",
    "audio": ".m4a",
    "file": "",  # 檔案類型會有自己的副檔名
}

# MIME 類型對應的副檔名
MIME_TO_EXTENSION = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/gif": ".gif",
    "image/webp": ".webp",
    "video/mp4": ".mp4",
    "audio/m4a": ".m4a",
    "audio/mp4": ".m4a",
    "audio/mpeg": ".mp3",
}

# Mention 佔位符常數
MENTION_KEY = "user"
MENTION_PLACEHOLDER = f"{{{MENTION_KEY}}} "  # "{user} "
