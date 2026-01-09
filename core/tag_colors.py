from __future__ import annotations

import hashlib

TAG_COLOR_CLASSES = (
    "tag-color-1",
    "tag-color-2",
    "tag-color-3",
    "tag-color-4",
    "tag-color-5",
)


def get_tag_color_class(tag_key: str) -> str:
    if not tag_key:
        return TAG_COLOR_CLASSES[0]
    digest = hashlib.md5(tag_key.encode("utf-8")).hexdigest()
    index = int(digest, 16) % len(TAG_COLOR_CLASSES)
    return TAG_COLOR_CLASSES[index]


def build_tag_items(tags):
    return [
        {
            "name": tag.name,
            "slug": tag.slug,
            "color_class": get_tag_color_class(tag.slug),
        }
        for tag in tags
    ]
