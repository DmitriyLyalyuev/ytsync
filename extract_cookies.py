#!/usr/bin/env python3
"""
Cookie Extractor for YouTube Sync Service
Извлекает куки из браузеров для обхода ограничений YouTube
"""

import argparse
import os
import subprocess
import sys
import tempfile


def extract_cookies(browser):
    """Извлечение кук через yt-dlp"""
    temp_file = f"{browser}_cookies.txt"
    
    try:
        # Вызываем yt-dlp для извлечения кук
        cmd = [
            'yt-dlp', 
            '--cookies-from-browser', browser,
            '--cookies', temp_file,
            '--no-download', 
            '--simulate',
            'https://youtube.com'
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        
        if result.returncode != 0:
            print(f"Ошибка yt-dlp: {result.stderr}", file=sys.stderr)
            return
        
        # Читаем файл кук
        if not os.path.exists(temp_file):
            print("Файл кук не создался", file=sys.stderr)
            return
            
        youtube_cookies = []
        with open(temp_file, 'r') as f:
            for line in f:
                line = line.strip()
                if line.startswith('#') or not line:
                    continue
                
                parts = line.split('\t')
                if len(parts) >= 7:
                    domain = parts[0]
                    name = parts[5]
                    value = parts[6]
                    
                    if 'youtube.com' in domain or 'google.com' in domain:
                        youtube_cookies.append(f"{name}={value}")
        
        # Удаляем временный файл
        os.unlink(temp_file)
        
        if youtube_cookies:
            cookie_string = "; ".join(youtube_cookies)
            print("cookies:")
            print("  enabled: true")
            print(f'  cookie_string: "{cookie_string}"')
        else:
            print("# YouTube куки не найдены")
            
    except Exception as e:
        print(f"Ошибка: {e}", file=sys.stderr)
        if os.path.exists(temp_file):
            os.unlink(temp_file)


def main():
    parser = argparse.ArgumentParser(description="Извлечение кук из браузеров")
    parser.add_argument("browser", choices=["chrome", "firefox", "safari"])
    args = parser.parse_args()
    
    extract_cookies(args.browser)


if __name__ == "__main__":
    main()