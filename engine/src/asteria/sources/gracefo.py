"""GRACE-FO 1 accelerometer-derived density (TU Delft TOLEOS v0003) from ESA's Swarm server.

Needs a free ESA EO Sign In account (ESA_EO_USER / ESA_EO_PASSWORD). Explicit FTP over TLS
with an encrypted data channel; certificates are verified. Raw files stay in the local cache.
"""

from __future__ import annotations

import ftplib
from datetime import date
from pathlib import Path

from asteria.config import setting

HOST = "swarm-diss.eo.esa.int"
ROOT = "/Multimission/GRACE-FO/DNS/Sat_1"
VERSION = "0003"


def name_for(day: date) -> str:
    d = day.strftime("%Y%m%d")
    return f"GF_OPER_DNS1ACC_2__{d}T000000_{d}T235959_{VERSION}.cdf"


def fetch(cache: Path, days: list[date]) -> list[Path]:
    missing = [d for d in days if not (cache / name_for(d)).is_file()]
    if missing:
        user, password = setting("ESA_EO_USER"), setting("ESA_EO_PASSWORD")
        if not user or not password:
            raise RuntimeError("ESA_EO_USER / ESA_EO_PASSWORD are not set")
        cache.mkdir(parents=True, exist_ok=True)
        ftp = ftplib.FTP_TLS(HOST, timeout=120)
        try:
            ftp.login(user, password)
            ftp.prot_p()
            for d in missing:
                out = cache / name_for(d)
                tmp = out.with_suffix(".part")
                with tmp.open("wb") as fh:
                    ftp.retrbinary(f"RETR {ROOT}/{d.year}/{name_for(d)}", fh.write)
                tmp.replace(out)
        finally:
            ftp.close()
    return [cache / name_for(d) for d in days]
