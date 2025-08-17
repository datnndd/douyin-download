#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import annotations

import sqlite3
import json
from typing import Any, Dict, Iterable, List, Optional, Tuple
from contextlib import contextmanager


def _j(value: Any) -> str:
    """JSON dump with ensure_ascii=False for Unicode URLs / nicknames."""
    return json.dumps(value, ensure_ascii=False)


class Database:
    def __init__(self, path: str = "data.db") -> None:
        self.path = path
        self.conn = sqlite3.connect(self.path)
        self.conn.row_factory = sqlite3.Row
        self._prepare()
        self.migrate()

    def _prepare(self) -> None:
        cur = self.conn.cursor()
        # Pragmas: WAL for write concurrency, FK for integrity, faster sync for scrape workloads
        cur.execute("PRAGMA journal_mode=WAL;")
        cur.execute("PRAGMA foreign_keys=ON;")
        cur.execute("PRAGMA synchronous=NORMAL;")
        cur.close()

    def close(self) -> None:
        try:
            self.conn.close()
        except Exception:
            pass

    @contextmanager
    def tx(self):
        cur = self.conn.cursor()
        try:
            yield cur
            self.conn.commit()
        except Exception:
            self.conn.rollback()
            raise
        finally:
            cur.close()

    # ---------------------------- Schema ---------------------------- #
    def migrate(self) -> None:
        with self.tx() as cur:
            cur.executescript(
                """
                CREATE TABLE IF NOT EXISTS dim_user (
                    sec_uid            TEXT PRIMARY KEY,
                    uid                TEXT,
                    unique_id          TEXT,
                    nickname           TEXT,
                    signature          TEXT,
                    follower_count     INTEGER,
                    following_count    INTEGER,
                    favoriting_count   INTEGER,
                    total_favorited    INTEGER,
                    short_id           TEXT,
                    user_age           TEXT,
                    prevent_download   TEXT,
                    secret             TEXT,
                    avatar_thumb       TEXT,   -- JSON
                    avatar             TEXT,   -- JSON (1080x if available)
                    cover_url          TEXT,   -- JSON
                    updated_at         TEXT
                );
                CREATE INDEX IF NOT EXISTS idx_user_unique_id ON dim_user(unique_id);

                CREATE TABLE IF NOT EXISTS dim_music (
                    music_id           TEXT PRIMARY KEY,
                    title              TEXT,
                    owner_handle       TEXT,
                    owner_id           TEXT,
                    owner_nickname     TEXT,
                    play_url           TEXT,   -- JSON
                    cover_hd           TEXT,   -- JSON
                    cover_large        TEXT,   -- JSON
                    cover_medium       TEXT,   -- JSON
                    cover_thumb        TEXT    -- JSON
                );

                CREATE TABLE IF NOT EXISTS dim_mix (
                    mix_id             TEXT PRIMARY KEY,
                    mix_name           TEXT,
                    is_serial_mix      TEXT,
                    mix_type           TEXT,
                    mix_pic_type       TEXT,
                    ids                TEXT,   -- JSON
                    cover_url          TEXT,   -- JSON
                    current_episode    TEXT,
                    updated_to_episode TEXT
                );

                CREATE TABLE IF NOT EXISTS fact_aweme (
                    aweme_id           TEXT PRIMARY KEY,
                    sec_uid            TEXT NOT NULL,
                    aweme_type         INTEGER,
                    create_time        TEXT,
                    desc               TEXT,
                    music_id           TEXT,
                    mix_id             TEXT,
                    statistics_json    TEXT,   -- full stats JSON
                    rawdata            TEXT,   -- full aweme JSON
                    FOREIGN KEY (sec_uid) REFERENCES dim_user(sec_uid) ON UPDATE CASCADE ON DELETE RESTRICT,
                    FOREIGN KEY (music_id) REFERENCES dim_music(music_id) ON UPDATE CASCADE ON DELETE SET NULL,
                    FOREIGN KEY (mix_id)   REFERENCES dim_mix(mix_id)   ON UPDATE CASCADE ON DELETE SET NULL
                );
                CREATE INDEX IF NOT EXISTS idx_aweme_sec_uid ON fact_aweme(sec_uid);
                CREATE INDEX IF NOT EXISTS idx_aweme_music_id ON fact_aweme(music_id);
                CREATE INDEX IF NOT EXISTS idx_aweme_mix_id   ON fact_aweme(mix_id);

                CREATE TABLE IF NOT EXISTS aweme_images (
                    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
                    aweme_id           TEXT NOT NULL,
                    idx                INTEGER NOT NULL,
                    uri                TEXT,
                    width              INTEGER,
                    height             INTEGER,
                    url_list           TEXT,   -- JSON
                    mask_url_list      TEXT,   -- JSON
                    UNIQUE(aweme_id, idx),
                    FOREIGN KEY (aweme_id) REFERENCES fact_aweme(aweme_id) ON DELETE CASCADE
                );
                CREATE INDEX IF NOT EXISTS idx_images_aweme_id ON aweme_images(aweme_id);

                CREATE TABLE IF NOT EXISTS aweme_video (
                    aweme_id           TEXT PRIMARY KEY,
                    play_addr_uri      TEXT,
                    play_addr_urls     TEXT,   -- JSON
                    cover_original     TEXT,   -- JSON
                    dynamic_cover      TEXT,   -- JSON
                    origin_cover       TEXT,   -- JSON
                    cover              TEXT,   -- JSON
                    FOREIGN KEY (aweme_id) REFERENCES fact_aweme(aweme_id) ON DELETE CASCADE
                );

                -- Associations for what *we* fetched (posts) and likes observed
                CREATE TABLE IF NOT EXISTS user_posts (
                    sec_uid            TEXT NOT NULL,
                    aweme_id           TEXT NOT NULL,
                    PRIMARY KEY (sec_uid, aweme_id),
                    FOREIGN KEY (sec_uid)  REFERENCES dim_user(sec_uid)  ON DELETE CASCADE,
                    FOREIGN KEY (aweme_id) REFERENCES fact_aweme(aweme_id) ON DELETE CASCADE
                );
                CREATE TABLE IF NOT EXISTS user_likes (
                    sec_uid            TEXT NOT NULL,
                    aweme_id           TEXT NOT NULL,
                    PRIMARY KEY (sec_uid, aweme_id),
                    FOREIGN KEY (sec_uid)  REFERENCES dim_user(sec_uid)  ON DELETE CASCADE,
                    FOREIGN KEY (aweme_id) REFERENCES fact_aweme(aweme_id) ON DELETE CASCADE
                );
                """
            )

    # ---------------------------- Upserts ---------------------------- #
    def upsert_user(self, author: Dict[str, Any]) -> None:
        if not author:
            return
        with self.tx() as cur:
            cur.execute(
                """
                INSERT INTO dim_user(
                    sec_uid, uid, unique_id, nickname, signature, follower_count, following_count,
                    favoriting_count, total_favorited, short_id, user_age, prevent_download, secret,
                    avatar_thumb, avatar, cover_url, updated_at
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,datetime('now'))
                ON CONFLICT(sec_uid) DO UPDATE SET
                    uid=excluded.uid,
                    unique_id=excluded.unique_id,
                    nickname=excluded.nickname,
                    signature=excluded.signature,
                    follower_count=excluded.follower_count,
                    following_count=excluded.following_count,
                    favoriting_count=excluded.favoriting_count,
                    total_favorited=excluded.total_favorited,
                    short_id=excluded.short_id,
                    user_age=excluded.user_age,
                    prevent_download=excluded.prevent_download,
                    secret=excluded.secret,
                    avatar_thumb=excluded.avatar_thumb,
                    avatar=excluded.avatar,
                    cover_url=excluded.cover_url,
                    updated_at=datetime('now');
                """,
                (
                    author.get("sec_uid"),
                    author.get("uid"),
                    author.get("unique_id"),
                    author.get("nickname"),
                    author.get("signature"),
                    author.get("follower_count"),
                    author.get("following_count"),
                    author.get("favoriting_count"),
                    author.get("total_favorited"),
                    author.get("short_id"),
                    author.get("user_age"),
                    author.get("prevent_download"),
                    author.get("secret"),
                    _j(author.get("avatar_thumb")),
                    _j(author.get("avatar")),
                    _j(author.get("cover_url")),
                ),
            )

    def upsert_music(self, music: Optional[Dict[str, Any]]) -> Optional[str]:
        if not music:
            return None
        # Some results might not carry a stable music id; fall back to title+owner_id if necessary
        music_id = music.get("mid") or music.get("music_id") or music.get("id") or None
        if not music_id:
            # Try from play_url.uri as last resort
            music_id = (music.get("play_url") or {}).get("uri")
        with self.tx() as cur:
            cur.execute(
                """
                INSERT INTO dim_music(
                    music_id, title, owner_handle, owner_id, owner_nickname, play_url,
                    cover_hd, cover_large, cover_medium, cover_thumb
                ) VALUES(?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(music_id) DO UPDATE SET
                    title=excluded.title,
                    owner_handle=excluded.owner_handle,
                    owner_id=excluded.owner_id,
                    owner_nickname=excluded.owner_nickname,
                    play_url=excluded.play_url,
                    cover_hd=excluded.cover_hd,
                    cover_large=excluded.cover_large,
                    cover_medium=excluded.cover_medium,
                    cover_thumb=excluded.cover_thumb;
                """,
                (
                    music_id,
                    music.get("title"),
                    music.get("owner_handle"),
                    music.get("owner_id"),
                    music.get("owner_nickname"),
                    _j(music.get("play_url")),
                    _j(music.get("cover_hd")),
                    _j(music.get("cover_large")),
                    _j(music.get("cover_medium")),
                    _j(music.get("cover_thumb")),
                ),
            )
        return music_id

    def upsert_mix(self, mix: Optional[Dict[str, Any]]) -> Optional[str]:
        if not mix:
            return None
        mix_id = mix.get("mix_id")
        if not mix_id:
            return None
        with self.tx() as cur:
            cur.execute(
                """
                INSERT INTO dim_mix(
                    mix_id, mix_name, is_serial_mix, mix_type, mix_pic_type, ids, cover_url,
                    current_episode, updated_to_episode
                ) VALUES(?,?,?,?,?,?,?,?,?)
                ON CONFLICT(mix_id) DO UPDATE SET
                    mix_name=excluded.mix_name,
                    is_serial_mix=excluded.is_serial_mix,
                    mix_type=excluded.mix_type,
                    mix_pic_type=excluded.mix_pic_type,
                    ids=excluded.ids,
                    cover_url=excluded.cover_url,
                    current_episode=excluded.current_episode,
                    updated_to_episode=excluded.updated_to_episode;
                """,
                (
                    mix_id,
                    mix.get("mix_name"),
                    mix.get("is_serial_mix"),
                    mix.get("mix_type"),
                    mix.get("mix_pic_type"),
                    _j(mix.get("ids")),
                    _j(mix.get("cover_url")),
                    (mix.get("statis") or {}).get("current_episode"),
                    (mix.get("statis") or {}).get("updated_to_episode"),
                ),
            )
        return mix_id

    def upsert_aweme(
            self,
            aweme: Dict[str, Any],
            is_user_post: bool = True,
            as_like_for_sec_uid: Optional[str] = None,
    ) -> None:
        """Insert/update a single aweme and all related entities.
        - If is_user_post: add to user_posts for its author.
        - If as_like_for_sec_uid: add to user_likes for that viewer.
        """
        if not aweme:
            return

        # 1) Users
        author = aweme.get("author") or {}
        self.upsert_user(author)
        sec_uid = author.get("sec_uid")

        # 2) Music / Mix
        music_id = self.upsert_music(aweme.get("music"))
        mix_id = self.upsert_mix(aweme.get("mix_info"))

        aweme_id = str(aweme.get("aweme_id"))
        statistics_json = _j(aweme.get("statistics"))

        with self.tx() as cur:
            cur.execute(
                """
                INSERT INTO fact_aweme(
                    aweme_id, sec_uid, aweme_type, create_time, desc, music_id, mix_id, statistics_json, rawdata
                ) VALUES(?,?,?,?,?,?,?,?,?)
                ON CONFLICT(aweme_id) DO UPDATE SET
                    sec_uid=excluded.sec_uid,
                    aweme_type=excluded.aweme_type,
                    create_time=excluded.create_time,
                    desc=excluded.desc,
                    music_id=excluded.music_id,
                    mix_id=excluded.mix_id,
                    statistics_json=excluded.statistics_json,
                    rawdata=excluded.rawdata;
                """,
                (
                    aweme_id,
                    sec_uid,
                    aweme.get("awemeType"),
                    aweme.get("create_time"),
                    aweme.get("desc"),
                    music_id,
                    mix_id,
                    statistics_json,
                    _j(aweme),
                ),
            )

        # 3) Images (for photo posts)
        images: List[Dict[str, Any]] = aweme.get("images") or []
        if images:
            with self.tx() as cur:
                for idx, img in enumerate(images):
                    cur.execute(
                        """
                        INSERT INTO aweme_images(aweme_id, idx, uri, width, height, url_list, mask_url_list)
                        VALUES(?,?,?,?,?,?,?)
                        ON CONFLICT(aweme_id, idx) DO UPDATE SET
                            uri=excluded.uri,
                            width=excluded.width,
                            height=excluded.height,
                            url_list=excluded.url_list,
                            mask_url_list=excluded.mask_url_list;
                        """,
                        (
                            aweme_id,
                            idx,
                            img.get("uri"),
                            _int_or_none(img.get("width")),
                            _int_or_none(img.get("height")),
                            _j(img.get("url_list")),
                            _j(img.get("mask_url_list")),
                        ),
                    )

        # 4) Video (for video posts)
        video = aweme.get("video") or {}
        play_addr = (video.get("play_addr") or {})
        if video or play_addr:
            with self.tx() as cur:
                cur.execute(
                    """
                    INSERT INTO aweme_video(
                        aweme_id, play_addr_uri, play_addr_urls, cover_original, dynamic_cover, origin_cover, cover
                    ) VALUES(?,?,?,?,?,?,?)
                    ON CONFLICT(aweme_id) DO UPDATE SET
                        play_addr_uri=excluded.play_addr_uri,
                        play_addr_urls=excluded.play_addr_urls,
                        cover_original=excluded.cover_original,
                        dynamic_cover=excluded.dynamic_cover,
                        origin_cover=excluded.origin_cover,
                        cover=excluded.cover;
                    """,
                    (
                        aweme_id,
                        play_addr.get("uri"),
                        _j(play_addr.get("url_list")),
                        _j(video.get("cover_original_scale")),
                        _j(video.get("dynamic_cover")),
                        _j(video.get("origin_cover")),
                        _j(video.get("cover")),
                    ),
                )

        # 5) Associations
        if is_user_post and sec_uid:
            with self.tx() as cur:
                cur.execute(
                    """
                    INSERT INTO user_posts(sec_uid, aweme_id) VALUES(?,?)
                    ON CONFLICT(sec_uid, aweme_id) DO NOTHING;
                    """,
                    (sec_uid, aweme_id),
                )
        if as_like_for_sec_uid:
            with self.tx() as cur:
                cur.execute(
                    """
                    INSERT INTO user_likes(sec_uid, aweme_id) VALUES(?,?)
                    ON CONFLICT(sec_uid, aweme_id) DO NOTHING;
                    """,
                    (as_like_for_sec_uid, aweme_id),
                )

    # ---------------------------- Helpers ---------------------------- #
    def bulk_upsert_awemes(
            self,
            aweme_list: Iterable[Dict[str, Any]],
            as_likes_for: Optional[str] = None,
            is_user_posts: bool = True,
    ) -> None:
        for aweme in aweme_list:
            self.upsert_aweme(aweme, is_user_post=is_user_posts, as_like_for_sec_uid=as_likes_for)

    # Simple getters for downstream ETL/exports
    def get_aweme(self, aweme_id: str) -> Optional[sqlite3.Row]:
        cur = self.conn.cursor()
        cur.execute("SELECT * FROM fact_aweme WHERE aweme_id=?", (aweme_id,))
        return cur.fetchone()

    def get_user(self, sec_uid: str) -> Optional[sqlite3.Row]:
        cur = self.conn.cursor()
        cur.execute("SELECT * FROM dim_user WHERE sec_uid=?", (sec_uid,))
        return cur.fetchone()

    def has_user_post(self, sec_uid: str, aweme_id: str) -> bool:
        cur = self.conn.cursor()
        cur.execute("SELECT 1 FROM user_posts WHERE sec_uid=? AND aweme_id=? LIMIT 1", (sec_uid, aweme_id))
        return cur.fetchone() is not None

    def has_user_like(self, sec_uid: str, aweme_id: str) -> bool:
        cur = self.conn.cursor()
        cur.execute("SELECT 1 FROM user_likes WHERE sec_uid=? AND aweme_id=? LIMIT 1", (sec_uid, aweme_id))
        return cur.fetchone() is not None


# ---------------------------- Utils ---------------------------- #

def _int_or_none(x: Any) -> Optional[int]:
    try:
        return int(x) if x is not None and x != "" else None
    except Exception:
        return None




if __name__ == "__main__":
    pass
