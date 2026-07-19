#!/usr/bin/env python3
"""Build the podcast feed(s) from exports and (when configured) push to R2.

Always writes each series' feed.xml to a local staging dir so it's inspectable
without any cloud setup. If AUDIOBOOK_DELIVERY_BASE_URL and the four R2_* settings
are present, it also uploads any not-yet-uploaded chapter mp3s plus the freshly
built feeds to the R2 bucket — the always-on host the phone's podcast app pulls
from. Safe to run on every export: uploads are incremental (skip objects already
in the bucket) and feeds are small.

Usage:
  publish_feed.py            # build locally; upload if configured
  publish_feed.py --no-upload  # build locally only
"""
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
BACKEND = SCRIPTS.parent / "backend"
sys.path.insert(0, str(BACKEND))

from src.config import get_settings  # noqa: E402
from src.delivery.feed import (  # noqa: E402
    build_all_feeds,
    discover_episodes,
    feed_key_for,
    prefixed,
)


def _local_feed_dir(settings) -> Path:
    return settings.exports_dir.parent / "feeds"


def _upload_configured(settings) -> bool:
    return bool(
        settings.delivery_base_url
        and settings.r2_bucket
        and settings.r2_endpoint_url
        and settings.r2_access_key_id
        and settings.r2_secret_access_key
    )


def _r2_client(settings):
    import boto3  # lazy — only needed when uploading

    return boto3.client(
        "s3",
        endpoint_url=settings.r2_endpoint_url,
        aws_access_key_id=settings.r2_access_key_id,
        aws_secret_access_key=settings.r2_secret_access_key,
        region_name="auto",
    )


def _existing_keys(client, bucket: str) -> set[str]:
    keys: set[str] = set()
    token = None
    while True:
        kw = {"Bucket": bucket}
        if token:
            kw["ContinuationToken"] = token
        resp = client.list_objects_v2(**kw)
        keys.update(o["Key"] for o in resp.get("Contents", []))
        if not resp.get("IsTruncated"):
            break
        token = resp.get("NextContinuationToken")
    return keys


def main() -> int:
    settings = get_settings()
    do_upload = "--no-upload" not in sys.argv and _upload_configured(settings)

    base_url = settings.delivery_base_url or "https://REPLACE-ME.example"
    prefix = settings.delivery_path_prefix
    feeds = build_all_feeds(settings.exports_dir, base_url, settings.delivery_author, prefix)

    # Always write feeds locally for inspection.
    feed_dir = _local_feed_dir(settings)
    for slug, xml in feeds.items():
        out = feed_dir / slug / "feed.xml"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(xml)
        print(f"feed: {out}  ->  {base_url}/{prefixed(feed_key_for(slug), prefix)}")

    if not feeds:
        print("No exported chapters found — nothing to publish.")
        return 0

    if not do_upload:
        if not _upload_configured(settings):
            print("Delivery not configured (set AUDIOBOOK_DELIVERY_BASE_URL + R2_*); "
                  "built feeds locally only.")
        return 0

    try:
        client = _r2_client(settings)
        existing = _existing_keys(client, settings.r2_bucket)
    except Exception as exc:  # missing boto3, bad creds, network
        print(f"Upload skipped — R2 client/list failed: {exc}", file=sys.stderr)
        return 0

    uploaded = 0
    for slug, episodes in discover_episodes(settings.exports_dir).items():
        for ep in episodes:
            key = prefixed(ep.object_key, prefix)
            if key in existing:
                continue
            with open(ep.path, "rb") as fh:
                client.put_object(
                    Bucket=settings.r2_bucket, Key=key,
                    Body=fh, ContentType="audio/mpeg",
                )
            uploaded += 1
            print(f"uploaded mp3: {key}")

    for slug, xml in feeds.items():
        key = prefixed(feed_key_for(slug), prefix)
        client.put_object(
            Bucket=settings.r2_bucket, Key=key,
            Body=xml.encode("utf-8"), ContentType="application/rss+xml",
        )
        print(f"uploaded feed: {key}")

    print(f"Done — {uploaded} new mp3(s), {len(feeds)} feed(s).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
