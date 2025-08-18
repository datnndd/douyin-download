#!/usr/bin/env python
# -*- coding: utf-8 -*-


import argparse
import json
import logging
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

import yaml

from src.douyin.douyinapi import DouyinApi
from src.douyin.download import Download
from src.douyin import douyin_headers
from src.common import utils
from logging.config import dictConfig


# ------------------------------ Logging ---------------------------------------

dictConfig({
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "rich": {
            "format": "%(asctime)s [%(levelname)s] %(name)s %(filename)s:%(lineno)d %(funcName)s | %(message)s"
        }
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "rich",
            "level": "INFO"
        }
    },
    "root": {
        "handlers": ["console"],
        "level": "INFO"
    },
})

log = logging.getLogger("Douyin")

# ------------------------------ Config ----------------------------------------

@dataclass
class Config:
    """All runtime options for the downloader."""
    link: List[str] = field(default_factory=list)
    path: str = ""

    music: bool = True
    cover: bool = True
    avatar: bool = True
    json: bool = True
    folderstyle: bool = True
    database: bool = True

    start_time: str = ""
    end_time: str = ""
    mode: List[str] = field(default_factory=lambda: ["post"])
    thread: int = 5
    cookie: Optional[str] = None

    number: Dict[str, int] = field(default_factory=lambda: {
        "post": 0, "like": 0, "allmix": 0, "mix": 0, "music": 0
    })
    increase: Dict[str, bool] = field(default_factory=lambda: {
        "post": False, "like": False
    })

    @classmethod
    def from_yaml(cls, yaml_path: str = "config.yaml") -> "Config":
        """
        Build config from YAML file. Missing/invalid file → keep defaults.
        Supports either `cookies: {k:v}` or `cookie: "k=v; ..."`.
        """
        cfg = cls()
        try:
            with open(yaml_path, "r", encoding="utf-8") as f:
                y = yaml.safe_load(f) or {}

            simple_fields = [
                "link", "path", "music", "cover", "avatar", "json",
                "start_time", "end_time", "folderstyle", "mode", "thread", "database"
            ]
            for key in simple_fields:
                if key in y:
                    setattr(cfg, key, y[key])

            # merge maps
            if "number" in y:
                cfg.number.update(y["number"] or {})
            if "increase" in y:
                cfg.increase.update(y["increase"] or {})

            # cookie sources
            if y.get("cookies"):
                cfg.cookie = "; ".join(f"{k}={v}" for k, v in (y["cookies"] or {}).items())

            # end_time special value
            if y.get("end_time") == "now":
                cfg.end_time = time.strftime("%Y-%m-%d", time.localtime())

        except FileNotFoundError:
            log.warning(f"Config file '{yaml_path}' not found — using defaults.")
        except Exception as e:
            log.error(f"Failed to parse '{yaml_path}': {e}")

        return cfg

    @classmethod
    def from_args(cls, args) -> "Config":
        """Build config from CLI arguments."""
        return cls(
            link=args.link,
            path=args.path,
            music=args.music,
            cover=args.cover,
            avatar=args.avatar,
            json=args.json,
            folderstyle=args.folderstyle,
            database=args.database,
            start_time="",
            end_time="",
            mode=args.mode if args.mode else ["post"],
            thread=max(1, int(args.thread or 5)),
            cookie=args.cookie or None,
            number={
                "post": args.postnumber,
                "like": args.likenumber,
                "allmix": args.allmixnumber,
                "mix": args.mixnumber,
                "music": args.musicnumber,
            },
            increase={
                "post": args.postincrease,
                "like": args.likeincrease,
                "allmix": args.allmixincrease,
                "mix": args.mixincrease,
                "music": args.musicincrease,
            },
        )

    def validate_and_prepare(self) -> bool:
        """Basic validation and ensure output path exists."""
        if not self.link:
            log.error("No link provided. Set at least one value under 'link'.")
            return False

        if not isinstance(self.thread, int) or self.thread <= 0:
            log.warning("Invalid thread count. Falling back to 5.")
            self.thread = 5

        # normalize path
        self.path = str(Path(self.path or os.getcwd()).resolve())
        Path(self.path).mkdir(parents=True, exist_ok=True)
        return True


# ------------------------------ Utilities -------------------------------------

def retry(max_retries: int = 3, delay_sec: int = 5):
    """Retry a function on failure, returning False/None when exhausted."""
    def decorator(fn):
        def wrapped(*args, **kwargs):
            for attempt in range(1, max_retries + 1):
                try:
                    result = fn(*args, **kwargs)
                    if result:
                        return result
                    raise RuntimeError("Empty/False result")
                except Exception as e:
                    if attempt >= max_retries:
                        log.error(f"[Retry] Exhausted ({max_retries}): {e}")
                        return None
                    log.warning(f"[Retry] Attempt {attempt}/{max_retries} failed: {e} — retry in {delay_sec}s")
                    time.sleep(delay_sec)
            return None

        return wrapped
    return decorator


def safe_name(value: str, fallback: str) -> str:
    """Sanitize file/folder names with a fallback."""
    if not value:
        return utils.replaceStr(fallback)
    return utils.replaceStr(value)


# ------------------------------ Core client -----------------------------------

class DouyinClient:

    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.api = DouyinApi(database_path="data.db" if cfg.database else None)
        self.downloader = Download(
            thread=cfg.thread,
            music=cfg.music,
            cover=cfg.cover,
            avatar=cfg.avatar,
            resjson=cfg.json,
            folderstyle=cfg.folderstyle,
        )
        # Inject cookie if provided
        if cfg.cookie:
            douyin_headers["Cookie"] = cfg.cookie

    # --------- public ---------

    def process_all(self) -> None:
        log.info(f"Output path: {self.cfg.path}")
        log.info(f"Threads: {self.cfg.thread}")
        t0 = time.time()

        for idx, link in enumerate(self.cfg.link, 1):
            log.info("-" * 80)
            log.info(f"[{idx}/{len(self.cfg.link)}] Processing: {link}")
            self._process_one(link)

        dt = int(time.time() - t0)
        log.info(f"\n[Done] Elapsed: {dt // 60}m {dt % 60}s\n")

    # --------- internal ---------

    def _process_one(self, link: str) -> None:
        try:
            url = self.api.getShareLink(link)
            key_type, key = self.api.getKey(url)
            if not key_type or not key:
                raise ValueError("Unrecognized link")

            handlers = {
                "user": self._handle_user,
                "mix": self._handle_mix,
                "music": self._handle_music,
                "aweme": self._handle_aweme,
                "live": self._handle_live,
            }
            handler = handlers.get(key_type)
            if not handler:
                log.warning(f"Unknown key type: {key_type}")
                return
            handler(key)
        except Exception as e:
            log.error(f"Failed to process link: {e}")

    def _handle_user(self, sec_uid: str) -> None:
        """Download user home based on selected modes (post/like/mix/music)."""
        log.info("Fetching user info…")
        peek = self.api.getUserInfoApi(sec_uid, "post", 1, 1)  # peek for nickname
        nickname = safe_name(peek[0].get("author", {}).get("nickname", ""), "unknown") if peek else "unknown"

        user_root = Path(self.cfg.path) / f"user_{nickname}_{sec_uid}"
        user_root.mkdir(exist_ok=True)

        for mode in self.cfg.mode:
            log.info(f"Mode: {mode}")
            target = user_root / mode
            target.mkdir(exist_ok=True)

            if mode == "mix":
                self._handle_user_all_mix(sec_uid, target)
            else:
                self._handle_user_posts_or_likes(sec_uid, mode, target)

    def _handle_user_posts_or_likes(self, sec_uid: str, mode: str, outdir: Path) -> None:
        data = self.api.getUserInfoApi(
            sec_uid=sec_uid,
            mode=mode,
            count=35,
            number=self.cfg.number.get(mode, 0),
            increase=self.cfg.increase.get(mode, False),
            start_time=self.cfg.start_time,
            end_time=self.cfg.end_time,
        )
        if not data:
            log.warning(f"No data for user {mode}.")
            return
        self.downloader.userDownload(awemeList=data, savePath=outdir)

    def _handle_user_all_mix(self, sec_uid: str, outdir: Path) -> None:
        mixes = self.api.getUserAllMixInfoApi(
            sec_uid=sec_uid,
            count=35,
            start_time=self.cfg.start_time,
            end_time=self.cfg.end_time,
        )
        if not mixes:
            log.warning("No mixes found on user home.")
            return

        for mix_id, mix_name in mixes.items():
            log.info(f"Downloading mix: {mix_name}")
            data = self.api.getMixInfoApi(
                mix_id=mix_id,
                count=35,
                number=0,
                start_time=self.cfg.start_time,
                end_time=self.cfg.end_time,
            )
            if not data:
                continue
            self.downloader.userDownload(awemeList=data, savePath=outdir / safe_name(mix_name, mix_id))

    @retry(max_retries=3, delay_sec=5)
    def _handle_mix(self, mix_id: str) -> bool:
        data = self.api.getMixInfoApi(
            mix_id=mix_id,
            count=35,
            number=self.cfg.number.get("mix", 0),
            start_time=self.cfg.start_time,
            end_time=self.cfg.end_time,
        )
        if not data:
            raise RuntimeError("Empty mix data")

        # try derive readable mix name
        first = data[0] if isinstance(data, list) and data else {}
        mix_name = safe_name(
            (first.get("mix_info") or {}).get("mix_name", "") or f"mix_{mix_id}",
            f"mix_{mix_id}",
        )

        outdir = Path(self.cfg.path) / f"{mix_name}_{mix_id}"
        outdir.mkdir(exist_ok=True)
        self.downloader.userDownload(awemeList=data, savePath=outdir)
        return True

    def _handle_music(self, music_id: str) -> None:
        data = self.api.getMusicInfo(
            music_id=music_id,
            count=35,
            number=self.cfg.number.get("music", 0),
            start_time=self.cfg.start_time,
            end_time=self.cfg.end_time,
        )
        if not data:
            log.warning("No items under music.")
            return

        first = data[0] if isinstance(data, list) and data else {}
        music_name = safe_name((first.get("music") or {}).get("title", ""), "music")

        outdir = Path(self.cfg.path) / f"music_{music_name}_{music_id}"
        outdir.mkdir(exist_ok=True)
        self.downloader.userDownload(awemeList=data, savePath=outdir)

    @retry(max_retries=3, delay_sec=5)
    def _handle_aweme(self, aweme_id: str) -> bool:
        d = self.api.getAwemeInfoApi(aweme_id)
        if not d:
            raise RuntimeError("Empty aweme data")

        # Basic sanity check (video type has play_addr)
        if d.get("awemeType") == 0:
            play_addrs = (d.get("video") or {}).get("play_addr", [])
            if not play_addrs:
                raise RuntimeError("Missing video URL")

        outdir = Path(self.cfg.path) / "aweme"
        outdir.mkdir(exist_ok=True)
        self.downloader.awemeDownload(d, savePath=outdir)
        log.info("Single aweme downloaded.")
        return True

    def _handle_live(self, web_rid: str) -> None:
        info, raw = self.api.getLiveInfoApi(web_rid) # type: ignore
        if not info:
            log.warning("No live info parsed.")
            return
        if not self.cfg.json:
            return

        outdir = Path(self.cfg.path) / "live"
        outdir.mkdir(exist_ok=True)
        name = safe_name(f"{web_rid}_{info.get('nickname', '')}", web_rid)
        with open(outdir / f"{name}.json", "w", encoding="utf-8") as f:
            json.dump(raw, f, ensure_ascii=False, indent=2)
        log.info("Live info saved to JSON.")


# ------------------------------ CLI -------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Douyin bulk downloader (readable refactor)")

    # Behavior source
    p.add_argument("--cmd", "-C", type=utils.str2bool, default=False,
                   help="Use CLI (True) or YAML (False). Default: False")
    p.add_argument("--config", "-F", default="config.yml", help="Path to YAML config")

    # Basic I/O
    p.add_argument("--link", "-l", action="append", default=[], help="Share URL / Web URL")
    p.add_argument("--path", "-p", default=os.getcwd(), help="Download output directory")
    p.add_argument("--thread", "-t", type=int, default=5, help="Thread count")

    # Toggles
    p.add_argument("--music", "-m", type=utils.str2bool, default=True, help="Download music")
    p.add_argument("--cover", "-c", type=utils.str2bool, default=True, help="Download cover")
    p.add_argument("--avatar", "-a", type=utils.str2bool, default=True, help="Download author avatar")
    p.add_argument("--json", "-j", type=utils.str2bool, default=True, help="Save response JSON")
    p.add_argument("--folderstyle", "-fs", type=utils.str2bool, default=True, help="Folder per video")

    # Modes
    p.add_argument("--mode", "-M", action="append", default=[], help="Modes: post/like/mix/music")

    # Limits + incremental flags
    for item in ["post", "like", "allmix", "mix", "music"]:
        p.add_argument(f"--{item}number", type=int, default=0, help=f"Limit for {item}")
        p.add_argument(f"--{item}increase", type=utils.str2bool, default=False, help=f"Incremental for {item}")

    # Misc
    p.add_argument("--database", "-d", type=utils.str2bool, default=True, help="Use database for history")
    p.add_argument("--cookie", type=str, default="", help="Raw Cookie header string")
    return p


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    cfg = Config.from_args(args) if args.cmd else Config.from_yaml(args.config)
    if not cfg.validate_and_prepare():
        return

    client = DouyinClient(cfg)
    client.process_all()


if __name__ == "__main__":
    main()
