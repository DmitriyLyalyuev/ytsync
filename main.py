#!/usr/bin/env python3
"""
YouTube Sync Service
Automatic synchronization of videos from YouTube channels and playlists
"""

import logging
import os
import random
import re
import sqlite3
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

import schedule
import yaml
import yt_dlp


def parse_netscape_cookies(file_path):
    """Parse cookies file"""
    cookie_pairs = []
    with open(file_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line.startswith("#") or not line:
                continue
            parts = line.split("\t")
            if len(parts) >= 7:
                domain = parts[0]
                name = parts[5]
                value = parts[6]
                if "youtube.com" in domain or "google.com" in domain:
                    cookie_pairs.append(f"{name}={value}")
    return cookie_pairs


class YouTubeSyncService:
    def __init__(self, config_path="config.yaml"):
        self.config_path = config_path
        self.config = None
        self.logger = None
        self.db_path = "./db/ytsync.db"
        self.config_last_modified = None
        self.load_config()
        self.setup_logging()
        self.init_database()

    def load_config(self):
        """Load configuration from YAML file"""
        try:
            with open(self.config_path, "r", encoding="utf-8") as file:
                self.config = yaml.safe_load(file)
            self.config_last_modified = os.path.getmtime(self.config_path)
        except FileNotFoundError:
            print(f"Config file {self.config_path} not found")
            sys.exit(1)
        except yaml.YAMLError as e:
            print(f"Error read config file: {e}")
            sys.exit(1)

    def setup_logging(self):
        """Logging"""
        log_config = self.config.get("logging", {})
        level = getattr(logging, log_config.get("level", "INFO").upper())
        format_str = log_config.get(
            "format", "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )

        logging.basicConfig(
            level=level, format=format_str, handlers=[logging.StreamHandler(sys.stdout)]
        )
        self.logger = logging.getLogger("YouTubeSync")

    def reload_config(self):
        """Reload config"""
        try:
            old_config = self.config.copy() if self.config else {}
            self.load_config()

            # Проверяем, изменились ли настройки логирования
            new_log_level = self.config.get("logging", {}).get("level", "INFO")
            old_log_level = old_config.get("logging", {}).get("level", "INFO")

            if new_log_level != old_log_level:
                self.setup_logging()
                self.logger.info("Logging settings updated")

            self.logger.info("Configuration successfully reloaded")

            new_db_path = "./db/ytsync.db"
            if hasattr(self, "db_path") and self.db_path != new_db_path:
                self.db_path = new_db_path
                self.init_database()
                self.logger.info("Database reinitialized")

        except Exception as e:
            if self.logger:
                self.logger.error(f"Error with config reload: {e}")
            else:
                print(f"Error with config reload: {e}")

    def check_config_changes(self):
        """Check config file changes"""
        try:
            current_modified = os.path.getmtime(self.config_path)
            if current_modified != self.config_last_modified:
                self.logger.info("Config file changed, reloading...")
                self.reload_config()
                return True
            return False
        except Exception as e:
            self.logger.error(f"Error with config reload: {e}")
            return False

    def init_database(self):
        """Database initialization"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS processed_videos (
                    video_id TEXT PRIMARY KEY,
                    url TEXT NOT NULL,
                    title TEXT,
                    upload_date TEXT,
                    processed_date TEXT,
                    status TEXT DEFAULT 'downloaded',
                    source_url TEXT
                )
            """
            )
            conn.commit()

    def is_video_processed(self, video_id):
        """Check if video is processed"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT status FROM processed_videos WHERE video_id = ?", (video_id,))
            result = cursor.fetchone()
            if result:
                status = result[0]
                return status == "downloaded" or status.startswith("skipped")
            return False

    def get_video_status(self, video_id):
        """Get video status from database"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT status, processed_date FROM processed_videos WHERE video_id = ?",
                (video_id,),
            )
            result = cursor.fetchone()
            return result if result else None

    def mark_video_processed(self, video_id, video_url, title, upload_date, source_url):
        """Mark video as successfully downloaded"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT OR REPLACE INTO processed_videos
                (video_id, url, title, upload_date, processed_date, status, source_url)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    video_id,
                    video_url,
                    title,
                    upload_date,
                    datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "downloaded",
                    source_url,
                ),
            )
            conn.commit()

    def mark_video_failed(self, video_id, video_url, title, upload_date, source_url, error_msg):
        """Mark video as failed"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT OR REPLACE INTO processed_videos
                (video_id, url, title, upload_date, processed_date, status, source_url)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    video_id,
                    video_url,
                    title,
                    upload_date,
                    datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    f"failed: {error_msg[:200]}",
                    source_url,
                ),
            )
            conn.commit()

    def mark_video_skipped(self, video_id, video_url, title, upload_date, source_url, reason):
        """Mark video as skipped"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT OR REPLACE INTO processed_videos
                (video_id, url, title, upload_date, processed_date, status, source_url)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    video_id,
                    video_url,
                    title,
                    upload_date,
                    datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    f"skipped: {reason}",
                    source_url,
                ),
            )
            conn.commit()

    def get_output_template(self, output_dir=None, source_url=None):
        """Create output filename template"""
        if output_dir is None:
            output_dir = self.config["download"]["output_dir"]

        # Plex TV Shows format for date-based shows
        # Structure: Season Year/Uploader - YYYY-MM-DD - VideoTitle.ext
        template = os.path.join(
            output_dir,
            "Season %(upload_date>%Y)s",
            "%(uploader)s - %(upload_date>%Y-%m-%d)s - %(title)s.%(ext)s",
        )

        self.logger.debug(f"Name template: {template}")
        return template

    def get_source_data(self):
        """Get source list and it's settings"""
        sources = []
        youtube_config = self.config.get("youtube", {})
        default_period = self.config["download"].get("default_period_days", 30)

        channels = youtube_config.get("channels", [])
        for channel in channels:
            if isinstance(channel, str):
                sources.append(
                    {
                        "url": channel,
                        "period_days": default_period,
                        "type": "channel",
                        "output_dir": self.config["download"]["output_dir"],
                    }
                )
            elif isinstance(channel, dict):
                sources.append(
                    {
                        "url": channel["url"],
                        "period_days": channel.get("period_days", default_period),
                        "type": "channel",
                        "output_dir": channel.get(
                            "output_dir", self.config["download"]["output_dir"]
                        ),
                    }
                )

        playlists = youtube_config.get("playlists", [])
        for playlist in playlists:
            if isinstance(playlist, str):
                sources.append(
                    {
                        "url": playlist,
                        "period_days": default_period,
                        "type": "playlist",
                        "output_dir": self.config["download"]["output_dir"],
                    }
                )
            elif isinstance(playlist, dict):
                sources.append(
                    {
                        "url": playlist["url"],
                        "period_days": playlist.get("period_days", default_period),
                        "type": "playlist",
                        "output_dir": playlist.get(
                            "output_dir", self.config["download"]["output_dir"]
                        ),
                    }
                )

        return sources

    def get_ydl_opts(self, period_days=None, output_dir=None, source_url=None):
        """Setting of yt-dlp with filter by date and miss blocks"""
        download_config = self.config["download"]

        max_videos_config = download_config.get("max_videos_per_source", 0)

        if max_videos_config > 0:
            max_videos = max_videos_config
        elif period_days and period_days > 0:
            max_videos = max(10, period_days * 3)
        else:
            max_videos = 50

        base_format = download_config.get(
            "quality", "bestvideo[height<=1080]+bestaudio/best[height<=720]/best"
        )

        http_headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }

        cookies_config = self.config.get("cookies", {})
        cookie_file_path = None

        if cookies_config.get("enabled", False):
            if "cookie_file" in cookies_config:
                file_path = cookies_config["cookie_file"]
                if os.path.exists(file_path):
                    cookie_file_path = file_path

        opts = {
            "format": base_format,
            "outtmpl": self.get_output_template(output_dir, source_url),
            "writeinfojson": False,
            "writesubtitles": False,
            "writeautomaticsub": False,
            "ignoreerrors": True,
            "no_warnings": False,
            "extract_flat": False,
            "playlist_end": max_videos,
            "merge_output_format": "mp4",
            "postprocessors": [
                {
                    "key": "FFmpegVideoConvertor",
                    "preferredformat": "mp4",
                },
                {
                    "key": "FFmpegMetadata",
                    "add_metadata": True,
                },
            ],
            "http_headers": http_headers,
            "sleep_interval": 1,
            "max_sleep_interval": 5,
            "retries": 3,
            "fragment_retries": 3,
            "skip_unavailable_fragments": True,
            "keep_fragments": False,
            "noprogress": False,
        }

        if cookie_file_path:
            opts["cookiefile"] = cookie_file_path
            self.logger.debug(f"🎯 Cookies added to yt-dlp settings: {cookie_file_path}")
        else:
            self.logger.debug("🎯 Download will be made without cookies")

        self.logger.info(f"Limit downloads with last {max_videos} files")

        max_file_size = download_config.get("max_file_size", 0)
        if max_file_size > 0:
            if "+" in base_format:
                opts["format"] = base_format.replace(
                    "bestvideo[height<=1080]", f"bestvideo[height<=1080][filesize<{max_file_size}M]"
                ).replace(
                    "bestvideo[height<=720]", f"bestvideo[height<=720][filesize<{max_file_size}M]"
                )
            else:
                opts["format"] += f"[filesize<{max_file_size}M]"

        filters = []

        if period_days and period_days > 0:
            cutoff_date = datetime.now() - timedelta(days=period_days)
            cutoff_date_str = cutoff_date.strftime("%Y%m%d")
            self.logger.info(
                f"Date filter set: downloading videos from the last {period_days} days (since {cutoff_date.strftime('%Y-%m-%d')})"
            )

            def date_filter(info_dict):
                upload_date = info_dict.get("upload_date")
                if not upload_date:
                    self.logger.debug(
                        f"Skipping video without date: {info_dict.get('title', 'Unknown')}"
                    )
                    return "Unknown date"

                if upload_date < cutoff_date_str:
                    self.logger.debug(
                        f"Skipping old video ({upload_date}): {info_dict.get('title', 'Unknown')}"
                    )
                    return f"Video too old: {upload_date}"

                self.logger.debug(
                    f"Accepting video ({upload_date}): {info_dict.get('title', 'Unknown')}"
                )
                return None

            filters.append(date_filter)

        max_duration = download_config.get("max_duration", 0)
        if max_duration > 0:

            def duration_filter(info_dict):
                duration = info_dict.get("duration", 0)
                if duration > max_duration:
                    self.logger.debug(
                        f"Skipping long video ({duration}s): {info_dict.get('title', 'Unknown')}"
                    )
                    return "Video too long"
                return None

            filters.append(duration_filter)

        if filters:

            def combined_filter(info_dict):
                for filter_func in filters:
                    result = filter_func(info_dict)
                    if result:
                        return result
                return None

            opts["match_filter"] = combined_filter

        return opts

    def download_from_source(self, source):
        """Loading video from source with error handling"""
        url = source["url"]
        period_days = source["period_days"]
        source_type = source["type"]
        output_dir = source["output_dir"]

        self.logger.info(
            f"Starting synchronization {source_type}: {url} (period: {period_days} days, folder: {output_dir})"
        )

        Path(output_dir).mkdir(parents=True, exist_ok=True)

        delay = random.uniform(2, 8)
        self.logger.debug(f"Wait for {delay:.1f} seconds before request")
        time.sleep(delay)

        # Логируем настройки кук
        cookies_config = self.config.get("cookies", {})
        if cookies_config.get("enabled", False):
            if "cookie_file" in cookies_config:
                file_path = cookies_config["cookie_file"]
                if os.path.exists(file_path):
                    self.logger.info(f"🍪 Using cookie file for {url}: {file_path}")
                    try:
                        cookie_pairs = parse_netscape_cookies(file_path)
                        if cookie_pairs:
                            self.logger.info(
                                f"🔑 Found {len(cookie_pairs)} YouTube cookies in file"
                            )
                        else:
                            self.logger.warning(
                                f"⚠️ Cookie file {file_path} does not contain YouTube cookies"
                            )
                    except Exception as e:
                        self.logger.error(f"❌ Error analyzing cookie file {file_path}: {e}")
                else:
                    self.logger.error(f"❌ Cookie file not found: {file_path}")
            else:
                self.logger.warning("⚠️ Cookies enabled but no cookie_file specified")
        else:
            self.logger.info("🚫 Cookies disabled in config - using basic authentication")

        max_retries = 3
        for attempt in range(max_retries):
            try:
                flat_opts = {"extract_flat": True, "quiet": True, "no_warnings": True}

                self.logger.info("Getting videos list from channel...")
                with yt_dlp.YoutubeDL(flat_opts) as flat_ydl:
                    info = flat_ydl.extract_info(url, download=False)
                self.logger.info("Video list obtained, starting filtering...")

                if "entries" in info:
                    entries = list(info["entries"])
                    filtered_urls = []

                    cutoff_date = None
                    if period_days and period_days > 0:
                        cutoff_date = datetime.now() - timedelta(days=period_days)
                        cutoff_date_str = cutoff_date.strftime("%Y%m%d")

                    info_opts = self.get_ydl_opts(period_days, output_dir, url)
                    info_opts.update({"quiet": True, "no_warnings": True, "extract_flat": False})
                    self.logger.debug(f"🔍 Using configured options for obtaining video metadata")

                    with yt_dlp.YoutubeDL(info_opts) as info_ydl:
                        for entry in entries:
                            if entry is None:
                                continue

                            video_id = entry.get("id")
                            if not video_id:
                                continue

                            if self.is_video_processed(video_id):
                                self.logger.debug(f"Skipping already processed video: {video_id}")
                                continue

                            video_url = f"https://www.youtube.com/watch?v={video_id}"

                            if cutoff_date:
                                try:
                                    video_info = info_ydl.extract_info(video_url, download=False)
                                    upload_date = video_info.get("upload_date")
                                    video_title = video_info.get("title", "Unknown")

                                    if not upload_date:
                                        self.logger.debug(
                                            f"Skipping video without date: {video_title}"
                                        )
                                        self.mark_video_skipped(
                                            video_id,
                                            video_url,
                                            video_title,
                                            "",
                                            url,
                                            "no upload date",
                                        )
                                        continue
                                    if upload_date < cutoff_date_str:
                                        self.logger.debug(
                                            f"Skipping old video ({upload_date}): {video_title}"
                                        )
                                        self.mark_video_skipped(
                                            video_id,
                                            video_url,
                                            video_title,
                                            upload_date,
                                            url,
                                            f'old video (before {cutoff_date.strftime("%Y-%m-%d")})',
                                        )
                                        continue
                                    self.logger.debug(
                                        f"Accepting video ({upload_date}): {video_title}"
                                    )
                                    filtered_urls.append(
                                        (video_url, video_id, video_title, upload_date)
                                    )
                                except Exception as e:
                                    self.logger.warning(
                                        f"Error getting metadata for {video_url}: {e}"
                                    )
                                    continue
                            else:
                                try:
                                    video_info = info_ydl.extract_info(video_url, download=False)
                                    video_title = video_info.get("title", "Unknown")
                                    upload_date = video_info.get("upload_date", "")
                                    filtered_urls.append(
                                        (video_url, video_id, video_title, upload_date)
                                    )
                                except Exception as e:
                                    self.logger.warning(
                                        f"Error getting metadata for {video_url}: {e}"
                                    )
                                    continue

                    total_videos = len(filtered_urls)
                    self.logger.info(
                        f"Found {total_videos} actual videos for download (out of {len(entries)} total)"
                    )

                    if total_videos == 0:
                        self.logger.info("No new videos to download")
                        if cookie_file_path:
                            self.logger.info(f"🍪 Cookies were used for checking videos from {url}")
                        else:
                            self.logger.info(
                                f"🚫 Checking videos from {url} was done without cookies"
                            )
                        return

                    download_opts = self.get_ydl_opts(period_days, output_dir, url)
                    download_opts.pop("match_filter", None)
                    with yt_dlp.YoutubeDL(download_opts) as download_ydl:
                        for video_data in filtered_urls:
                            video_url, video_id, video_title, upload_date = video_data

                            video_status = self.get_video_status(video_id)
                            if video_status and video_status[0].startswith("failed"):
                                self.logger.info(
                                    f"Retrying download: {video_title} ({video_id}) - previous error: {video_status[1]}"
                                )
                            else:
                                self.logger.info(f"Downloading: {video_title} ({video_id})")

                            try:
                                download_ydl.download([video_url])
                                self.mark_video_processed(
                                    video_id, video_url, video_title, upload_date, url
                                )
                                self.logger.info(
                                    f"✓ Video {video_id} downloaded successfully and marked as processed"
                                )
                            except Exception as e:
                                error_msg = str(e)
                                self.logger.error(f"✗ Error downloading {video_url}: {error_msg}")
                                # Mark video as failed
                                self.mark_video_failed(
                                    video_id, video_url, video_title, upload_date, url, error_msg
                                )
                                self.logger.debug(
                                    f"Video {video_id} marked as failed, will retry on next run"
                                )
                else:
                    self.logger.info("Downloading single video")
                    download_opts = self.get_ydl_opts(period_days, output_dir, url)
                    with yt_dlp.YoutubeDL(download_opts) as download_ydl:
                        download_ydl.download([url])

                self.logger.info(f"Successfully completed synchronization: {url}")
                break

            except yt_dlp.utils.DownloadError as e:
                error_msg = str(e)
                if "HTTP Error 400" in error_msg or "Precondition check failed" in error_msg:
                    self.logger.warning(
                        f"Error YouTube API for {url} (retry {attempt + 1}/{max_retries}): {error_msg}"
                    )
                    if attempt < max_retries - 1:
                        retry_delay = random.uniform(10, 30) * (attempt + 1)
                        self.logger.info(f"Waiting {retry_delay:.1f} seconds before retry")
                        time.sleep(retry_delay)
                    else:
                        self.logger.error(
                            f"Can't complete synchronization {url} after {max_retries} attempts"
                        )
                else:
                    self.logger.error(f"Error with download {url}: {error_msg}")
                    break

            except Exception as e:
                self.logger.error(f"Unexpected error with {url}: {str(e)}")
                if attempt < max_retries - 1:
                    retry_delay = random.uniform(5, 15)
                    self.logger.info(f"Waiting {retry_delay:.1f} seconds before retry")
                    time.sleep(retry_delay)
                else:
                    break

    def sync_all(self):
        """Synchronization all sources from config"""
        self.logger.info("=== Synchronization starts ===")

        sources = self.get_source_data()

        if not sources:
            self.logger.warning("No sources found")
            return

        self.logger.info(f"Found {len(sources)} sources to sync")

        for i, source in enumerate(sources, 1):
            self.logger.info(f"[{i}/{len(sources)}] Processing: {source['url']}")
            self.download_from_source(source)

        self.logger.info("=== Synchronization completed ===")

    def setup_scheduler(self):
        """Setup scheduler"""
        scheduler_config = self.config.get("scheduler", {})
        interval_hours = scheduler_config.get("sync_interval_hours", 6)
        first_run_time = scheduler_config.get("first_run_time", "08:00")

        schedule.every(interval_hours).hours.do(self.sync_all)

        schedule.every().day.at(first_run_time).do(self.sync_all)

        self.logger.info(
            f"Scheduler set: every {interval_hours} hours, first run at {first_run_time}"
        )

    def run(self):
        """Main loop"""
        self.logger.info("YouTube Sync Service started")

        self.sync_all()

        self.setup_scheduler()

        try:
            cycle_count = 0
            while True:
                cycle_count += 1
                schedule.run_pending()

                if cycle_count % 10 == 0:
                    self.check_config_changes()

                time.sleep(60)
        except KeyboardInterrupt:
            self.logger.info("Got signal to stop. Exiting...")
        except Exception as e:
            self.logger.error(f"Critical error: {str(e)}")


def main():
    """Main function"""
    service = YouTubeSyncService()
    service.run()


if __name__ == "__main__":
    main()
