#!/usr/bin/env python3
"""
YouTube Sync Service
Автоматическая синхронизация видео с YouTube каналов и плейлистов
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
    """Парсинг файла кук в формате Netscape"""
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
        """Загрузка конфигурации из YAML файла"""
        try:
            with open(self.config_path, "r", encoding="utf-8") as file:
                self.config = yaml.safe_load(file)
            # Запоминаем время изменения файла
            self.config_last_modified = os.path.getmtime(self.config_path)
        except FileNotFoundError:
            print(f"Файл конфигурации {self.config_path} не найден")
            sys.exit(1)
        except yaml.YAMLError as e:
            print(f"Ошибка при чтении конфигурации: {e}")
            sys.exit(1)

    def setup_logging(self):
        """Настройка логирования"""
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
        """Перезагрузка конфигурации"""
        try:
            old_config = self.config.copy() if self.config else {}
            self.load_config()

            # Проверяем, изменились ли настройки логирования
            new_log_level = self.config.get("logging", {}).get("level", "INFO")
            old_log_level = old_config.get("logging", {}).get("level", "INFO")

            if new_log_level != old_log_level:
                self.setup_logging()
                self.logger.info("Настройки логирования обновлены")

            self.logger.info("Конфигурация успешно перезагружена")

            # Обновляем путь к базе данных если он изменился
            new_db_path = "./db/ytsync.db"  # или из конфига если добавите
            if hasattr(self, "db_path") and self.db_path != new_db_path:
                self.db_path = new_db_path
                self.init_database()
                self.logger.info("База данных переинициализирована")

        except Exception as e:
            if self.logger:
                self.logger.error(f"Ошибка при перезагрузке конфигурации: {e}")
            else:
                print(f"Ошибка при перезагрузке конфигурации: {e}")

    def check_config_changes(self):
        """Проверяет изменения в файле конфигурации"""
        try:
            current_modified = os.path.getmtime(self.config_path)
            if current_modified != self.config_last_modified:
                self.logger.info("Обнаружены изменения в файле конфигурации, перезагружаю...")
                self.reload_config()
                return True
            return False
        except Exception as e:
            self.logger.error(f"Ошибка при проверке конфигурации: {e}")
            return False

    def init_database(self):
        """Инициализация базы данных"""
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
        """Проверяет, было ли видео уже обработано (загружено или пропущено)"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT status FROM processed_videos WHERE video_id = ?", (video_id,))
            result = cursor.fetchone()
            if result:
                status = result[0]
                # Считаем обработанными только загруженные и пропущенные видео
                # Неудачные попытки (failed) будут повторяться
                return status == "downloaded" or status.startswith("skipped")
            return False

    def get_video_status(self, video_id):
        """Получает статус видео из базы данных"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT status, processed_date FROM processed_videos WHERE video_id = ?",
                (video_id,),
            )
            result = cursor.fetchone()
            return result if result else None

    def mark_video_processed(self, video_id, video_url, title, upload_date, source_url):
        """Отмечает видео как успешно загруженное"""
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
        """Отмечает видео как неудачно загруженное"""
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
        """Отмечает видео как пропущенное (по дате, длительности и т.д.)"""
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

    def sanitize_filename(self, filename):
        """Очистка имени файла от недопустимых символов"""
        # Удаляем недопустимые символы для файловой системы
        filename = re.sub(r'[<>:"/\\|?*]', "", filename)
        # Ограничиваем длину имени файла
        if len(filename) > 200:
            filename = filename[:200]
        return filename.strip()

    def get_output_template(self, output_dir=None, source_url=None):
        """Создание шаблона для именования файлов по стандарту Plex TV Shows"""
        if output_dir is None:
            output_dir = self.config["download"]["output_dir"]

        # Plex TV Shows формат для date-based shows
        # Структура: ShowName (Year)/Season Year/ShowName - YYYY-MM-DD - EpisodeTitle.ext
        template = os.path.join(
            output_dir,
            "Season %(upload_date>%Y)s",
            "%(uploader)s - %(upload_date>%Y-%m-%d)s - %(title)s.%(ext)s",
        )

        self.logger.debug(f"Шаблон именования: {template}")
        return template

    def get_source_data(self):
        """Получение списка всех источников с их настройками"""
        sources = []
        youtube_config = self.config.get("youtube", {})
        default_period = self.config["download"].get("default_period_days", 30)

        # Обработка каналов
        channels = youtube_config.get("channels", [])
        for channel in channels:
            if isinstance(channel, str):
                # Старый формат - простая строка
                sources.append(
                    {
                        "url": channel,
                        "period_days": default_period,
                        "type": "channel",
                        "output_dir": self.config["download"][
                            "output_dir"
                        ],  # Используем общую папку
                    }
                )
            elif isinstance(channel, dict):
                # Новый формат - словарь с настройками
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

        # Обработка плейлистов
        playlists = youtube_config.get("playlists", [])
        for playlist in playlists:
            if isinstance(playlist, str):
                # Старый формат - простая строка
                sources.append(
                    {
                        "url": playlist,
                        "period_days": default_period,
                        "type": "playlist",
                        "output_dir": self.config["download"][
                            "output_dir"
                        ],  # Используем общую папку
                    }
                )
            elif isinstance(playlist, dict):
                # Новый формат - словарь с настройками
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
        """Настройки для yt-dlp с фильтром по дате и обходом блокировок"""
        download_config = self.config["download"]

        # Вычисляем максимальное количество видео для обработки
        max_videos_config = download_config.get("max_videos_per_source", 0)

        if max_videos_config > 0:
            # Используем настройку из конфига
            max_videos = max_videos_config
        elif period_days and period_days > 0:
            # Автоматически: примерно 1-2 видео в день для активного канала
            max_videos = max(10, period_days * 3)
        else:
            # По умолчанию
            max_videos = 50

        # Получаем формат качества и обрабатываем дополнительные ограничения
        base_format = download_config.get(
            "quality", "bestvideo[height<=1080]+bestaudio/best[height<=720]/best"
        )

        # Базовые HTTP заголовки
        http_headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }

        # Обрабатываем куки если они настроены
        cookies_config = self.config.get("cookies", {})
        cookie_file_path = None

        if cookies_config.get("enabled", False):
            if "cookie_file" in cookies_config:
                # Используем файл кук напрямую в yt-dlp
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
            # Ограничиваем количество обрабатываемых видео
            "playlist_end": max_videos,
            # Для высокого качества нужен merge
            "merge_output_format": "mp4",
            # Постпроцессоры для обеспечения совместимости с Plex
            "postprocessors": [
                {
                    "key": "FFmpegVideoConvertor",
                    "preferedformat": "mp4",
                },
                {
                    "key": "FFmpegMetadata",
                    "add_metadata": True,
                },
            ],
            # Настройки для обхода блокировок YouTube
            "http_headers": http_headers,
            "sleep_interval": 1,  # Минимальная задержка между запросами
            "max_sleep_interval": 5,  # Максимальная задержка
            "retries": 3,  # Количество повторов
            "fragment_retries": 3,
            "skip_unavailable_fragments": True,
            "keep_fragments": False,
            "noprogress": False,
        }

        # Добавляем куки в опции yt-dlp
        if cookie_file_path:
            opts["cookiefile"] = cookie_file_path
            self.logger.debug(f"🎯 Добавлен cookiefile в опции yt-dlp для загрузки: {cookie_file_path}")
        else:
            self.logger.debug("🎯 Загрузка будет выполнена без кук")

        self.logger.info(f"Ограничиваем обработку максимум {max_videos} последними видео")

        # Ограничения по размеру - применяем к базовому формату
        max_file_size = download_config.get("max_file_size", 0)
        if max_file_size > 0:
            # Для сложных форматов с + нужно добавлять ограничение к каждой части
            if "+" in base_format:
                # Применяем ограничение к видео части
                opts["format"] = base_format.replace(
                    "bestvideo[height<=1080]", f"bestvideo[height<=1080][filesize<{max_file_size}M]"
                ).replace(
                    "bestvideo[height<=720]", f"bestvideo[height<=720][filesize<{max_file_size}M]"
                )
            else:
                opts["format"] += f"[filesize<{max_file_size}M]"

        # Создаем комбинированный фильтр
        filters = []

        # Фильтр по дате
        if period_days and period_days > 0:
            cutoff_date = datetime.now() - timedelta(days=period_days)
            cutoff_date_str = cutoff_date.strftime("%Y%m%d")
            self.logger.info(
                f"Установлен фильтр по дате: загружаем видео за последние {period_days} дней (с {cutoff_date.strftime('%Y-%m-%d')})"
            )

            def date_filter(info_dict):
                upload_date = info_dict.get("upload_date")
                if not upload_date:
                    self.logger.debug(
                        f"Пропускаем видео без даты: {info_dict.get('title', 'Неизвестно')}"
                    )
                    return "Неизвестная дата загрузки"

                if upload_date < cutoff_date_str:
                    self.logger.debug(
                        f"Пропускаем старое видео ({upload_date}): {info_dict.get('title', 'Неизвестно')}"
                    )
                    return f"Видео слишком старое: {upload_date}"

                self.logger.debug(
                    f"Принимаем видео ({upload_date}): {info_dict.get('title', 'Неизвестно')}"
                )
                return None

            filters.append(date_filter)

        # Фильтр по длительности
        max_duration = download_config.get("max_duration", 0)
        if max_duration > 0:

            def duration_filter(info_dict):
                duration = info_dict.get("duration", 0)
                if duration > max_duration:
                    self.logger.debug(
                        f"Пропускаем длинное видео ({duration}s): {info_dict.get('title', 'Неизвестно')}"
                    )
                    return "Видео слишком длинное"
                return None

            filters.append(duration_filter)

        # Применяем комбинированный фильтр
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
        """Загрузка видео с указанного источника с обработкой ошибок"""
        url = source["url"]
        period_days = source["period_days"]
        source_type = source["type"]
        output_dir = source["output_dir"]

        self.logger.info(
            f"Начинаю синхронизацию {source_type}: {url} (период: {period_days} дней, папка: {output_dir})"
        )

        # Создаем папку для загрузки если она не существует
        Path(output_dir).mkdir(parents=True, exist_ok=True)

        # Случайная задержка перед запросом для снижения нагрузки
        delay = random.uniform(2, 8)
        self.logger.debug(f"Ожидание {delay:.1f} секунд перед запросом")
        time.sleep(delay)

        # Получаем и логируем настройки кук
        cookies_config = self.config.get("cookies", {})
        cookie_file_path = None
        
        if cookies_config.get("enabled", False):
            if "cookie_file" in cookies_config:
                file_path = cookies_config["cookie_file"]
                if os.path.exists(file_path):
                    cookie_file_path = file_path
                    self.logger.info(f"🍪 Используем файл кук для {url}: {file_path}")
                    
                    # Диагностика содержимого файла кук
                    try:
                        cookie_pairs = parse_netscape_cookies(file_path)
                        if cookie_pairs:
                            self.logger.info(f"🔑 Найдено {len(cookie_pairs)} YouTube кук в файле")
                        else:
                            self.logger.warning(f"⚠️ Файл кук {file_path} не содержит YouTube кук")
                    except Exception as e:
                        self.logger.error(f"❌ Ошибка при анализе файла кук {file_path}: {e}")
                else:
                    self.logger.error(f"❌ Файл кук не найден: {file_path}")
            else:
                self.logger.warning("⚠️ Куки включены, но не указан cookie_file")
        else:
            self.logger.info("🚫 Куки отключены в конфигурации - используется базовая аутентификация")

        max_retries = 3
        for attempt in range(max_retries):
            try:
                # Сначала получаем только список видео без загрузки метаданных
                flat_opts = {"extract_flat": True, "quiet": True, "no_warnings": True}

                self.logger.info("Получаем список видео с канала...")
                with yt_dlp.YoutubeDL(flat_opts) as flat_ydl:
                    info = flat_ydl.extract_info(url, download=False)
                self.logger.info("Список видео получен, начинаем фильтрацию...")

                if "entries" in info:
                    # Применяем фильтры к entries для подсчета актуальных видео
                    entries = list(info["entries"])
                    filtered_urls = []

                    # Применяем фильтр по дате если он установлен
                    cutoff_date = None
                    if period_days and period_days > 0:
                        cutoff_date = datetime.now() - timedelta(days=period_days)
                        cutoff_date_str = cutoff_date.strftime("%Y%m%d")

                    # Создаем экземпляр для получения метаданных отдельных видео
                    info_opts = {"quiet": True, "no_warnings": True}
                    # Добавляем куки в опции для получения метаданных
                    if cookie_file_path:
                        info_opts["cookiefile"] = cookie_file_path
                        self.logger.debug(f"🔍 Используем куки для получения метаданных видео")
                    else:
                        self.logger.debug(f"🔍 Получаем метаданные видео без кук")

                    with yt_dlp.YoutubeDL(info_opts) as info_ydl:
                        for entry in entries:
                            if entry is None:
                                continue

                            video_id = entry.get("id")
                            if not video_id:
                                continue

                            # Проверяем, было ли видео уже обработано (загружено или пропущено)
                            if self.is_video_processed(video_id):
                                self.logger.debug(f"Пропускаем уже обработанное видео: {video_id}")
                                continue

                            video_url = f"https://www.youtube.com/watch?v={video_id}"

                            # Получаем метаданные видео для проверки даты
                            if cutoff_date:
                                try:
                                    video_info = info_ydl.extract_info(video_url, download=False)
                                    upload_date = video_info.get("upload_date")
                                    video_title = video_info.get("title", "Неизвестно")

                                    if not upload_date:
                                        self.logger.debug(
                                            f"Пропускаем видео без даты: {video_title}"
                                        )
                                        self.mark_video_skipped(
                                            video_id,
                                            video_url,
                                            video_title,
                                            "",
                                            url,
                                            "нет даты загрузки",
                                        )
                                        continue
                                    if upload_date < cutoff_date_str:
                                        self.logger.debug(
                                            f"Пропускаем старое видео ({upload_date}): {video_title}"
                                        )
                                        self.mark_video_skipped(
                                            video_id,
                                            video_url,
                                            video_title,
                                            upload_date,
                                            url,
                                            f'старое видео (до {cutoff_date.strftime("%Y-%m-%d")})',
                                        )
                                        continue
                                    self.logger.debug(
                                        f"Принимаем видео ({upload_date}): {video_title}"
                                    )
                                    filtered_urls.append(
                                        (video_url, video_id, video_title, upload_date)
                                    )
                                except Exception as e:
                                    self.logger.warning(
                                        f"Ошибка при получении метаданных для {video_url}: {e}"
                                    )
                                    continue
                            else:
                                # Если фильтр по дате не установлен, получаем метаданные для записи в базу
                                try:
                                    video_info = info_ydl.extract_info(video_url, download=False)
                                    video_title = video_info.get("title", "Неизвестно")
                                    upload_date = video_info.get("upload_date", "")
                                    filtered_urls.append(
                                        (video_url, video_id, video_title, upload_date)
                                    )
                                except Exception as e:
                                    self.logger.warning(
                                        f"Ошибка при получении метаданных для {video_url}: {e}"
                                    )
                                    continue

                    total_videos = len(filtered_urls)
                    self.logger.info(
                        f"Найдено {total_videos} актуальных видео для загрузки (из {len(entries)} всего)"
                    )

                    if total_videos == 0:
                        self.logger.info("Нет новых видео для загрузки")
                        # Показываем диагностику кук даже если нет видео для загрузки
                        if cookie_file_path:
                            self.logger.info(f"🍪 Куки были использованы для проверки видео с {url}")
                        else:
                            self.logger.info(f"🚫 Проверка видео с {url} выполнена без кук")
                        return

                    # Загружаем только отфильтрованные видео
                    download_opts = self.get_ydl_opts(period_days, output_dir, url)
                    # Убираем match_filter так как мы уже отфильтровали
                    download_opts.pop("match_filter", None)
                    with yt_dlp.YoutubeDL(download_opts) as download_ydl:
                        for video_data in filtered_urls:
                            video_url, video_id, video_title, upload_date = video_data

                            # Проверяем, была ли предыдущая неудачная попытка
                            video_status = self.get_video_status(video_id)
                            if video_status and video_status[0].startswith("failed"):
                                self.logger.info(
                                    f"Повторная попытка загрузки: {video_title} ({video_id}) - предыдущая ошибка: {video_status[1]}"
                                )
                            else:
                                self.logger.info(f"Загружаем: {video_title} ({video_id})")

                            try:
                                download_ydl.download([video_url])
                                # Отмечаем видео как успешно загруженное только после успешной загрузки
                                self.mark_video_processed(
                                    video_id, video_url, video_title, upload_date, url
                                )
                                self.logger.info(
                                    f"✓ Видео {video_id} успешно загружено и отмечено как обработанное"
                                )
                            except Exception as e:
                                error_msg = str(e)
                                self.logger.error(f"✗ Ошибка при загрузке {video_url}: {error_msg}")
                                # Отмечаем видео как неудачно загруженное
                                self.mark_video_failed(
                                    video_id, video_url, video_title, upload_date, url, error_msg
                                )
                                self.logger.debug(
                                    f"Видео {video_id} отмечено как неудачное, будет повторена попытка при следующем запуске"
                                )
                else:
                    # Одиночное видео
                    self.logger.info("Загружаю одиночное видео")
                    download_opts = self.get_ydl_opts(period_days, output_dir, url)
                    with yt_dlp.YoutubeDL(download_opts) as download_ydl:
                        download_ydl.download([url])

                # Если дошли до сюда, значит всё прошло успешно
                self.logger.info(f"Успешно завершена синхронизация: {url}")
                break

            except yt_dlp.utils.DownloadError as e:
                error_msg = str(e)
                if "HTTP Error 400" in error_msg or "Precondition check failed" in error_msg:
                    self.logger.warning(
                        f"Ошибка YouTube API для {url} (попытка {attempt + 1}/{max_retries}): {error_msg}"
                    )
                    if attempt < max_retries - 1:
                        # Увеличиваем задержку при повторе
                        retry_delay = random.uniform(10, 30) * (attempt + 1)
                        self.logger.info(f"Ожидание {retry_delay:.1f} секунд перед повтором")
                        time.sleep(retry_delay)
                    else:
                        self.logger.error(f"Не удалось загрузить {url} после {max_retries} попыток")
                else:
                    self.logger.error(f"Ошибка при загрузке {url}: {error_msg}")
                    break

            except Exception as e:
                self.logger.error(f"Неожиданная ошибка при загрузке {url}: {str(e)}")
                if attempt < max_retries - 1:
                    retry_delay = random.uniform(5, 15)
                    self.logger.info(f"Ожидание {retry_delay:.1f} секунд перед повтором")
                    time.sleep(retry_delay)
                else:
                    break

    def sync_all(self):
        """Синхронизация всех источников из конфигурации"""
        self.logger.info("=== Начало синхронизации ===")

        # Получаем все источники с их настройками
        sources = self.get_source_data()

        if not sources:
            self.logger.warning("Не найдено источников для синхронизации")
            return

        self.logger.info(f"Найдено {len(sources)} источников для синхронизации")

        # Синхронизация каждого источника
        for i, source in enumerate(sources, 1):
            self.logger.info(f"[{i}/{len(sources)}] Обработка: {source['url']}")
            self.download_from_source(source)

        self.logger.info("=== Синхронизация завершена ===")

    def setup_scheduler(self):
        """Настройка планировщика задач"""
        scheduler_config = self.config.get("scheduler", {})
        interval_hours = scheduler_config.get("sync_interval_hours", 6)
        first_run_time = scheduler_config.get("first_run_time", "08:00")

        # Планируем регулярную синхронизацию
        schedule.every(interval_hours).hours.do(self.sync_all)

        # Планируем первый запуск в определенное время
        schedule.every().day.at(first_run_time).do(self.sync_all)

        self.logger.info(
            f"Планировщик настроен: каждые {interval_hours} часов, первый запуск в {first_run_time}"
        )

    def run(self):
        """Основной цикл работы сервиса"""
        self.logger.info("YouTube Sync Service запущен")

        # Выполняем первую синхронизацию сразу
        self.sync_all()

        # Настраиваем планировщик
        self.setup_scheduler()

        # Основной цикл
        try:
            cycle_count = 0
            while True:
                cycle_count += 1
                schedule.run_pending()

                # Проверяем конфигурацию каждые 10 циклов (10 минут)
                if cycle_count % 10 == 0:
                    self.check_config_changes()

                time.sleep(60)  # Проверяем каждую минуту
        except KeyboardInterrupt:
            self.logger.info("Получен сигнал остановки. Завершение работы...")
        except Exception as e:
            self.logger.error(f"Критическая ошибка: {str(e)}")


def main():
    """Точка входа в приложение"""
    service = YouTubeSyncService()
    service.run()


if __name__ == "__main__":
    main()
