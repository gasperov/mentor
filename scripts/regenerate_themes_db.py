#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import unicodedata
from dataclasses import dataclass
from datetime import datetime, timezone
from html import unescape
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from urllib.error import URLError
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen

BASE_DIR = Path(__file__).resolve().parents[1]
OUTPUT_PATH = BASE_DIR / "data" / "themes_database.json"


SOURCES: list[dict[str, str]] = [
    {
        "id": "gov_os",
        "label": "Programi in uÄŤni naÄŤrti v osnovni Ĺˇoli",
        "url": "https://www.gov.si/teme/programi-in-ucni-nacrti-v-osnovni-soli/",
        "type": "official_curriculum",
    },
    {
        "id": "ric_sm_predmeti",
        "label": "RIC - Predmeti sploĹˇne mature",
        "url": "https://www.ric.si/splosna-matura/predmeti/",
        "type": "official_exam_subjects",
    },
    {
        "id": "ric_pm_predmeti",
        "label": "RIC - Predmeti poklicne mature",
        "url": "https://www.ric.si/poklicna-matura/predmeti/",
        "type": "official_exam_subjects",
    },
    {
        "id": "gov_srednjesolski_programi",
        "label": "SrednjeĹˇolski izobraĹľevalni programi",
        "url": "https://www.gov.si/teme/srednjesolski-izobrazevalni-programi/",
        "type": "official_program_registry",
    },
    {
        "id": "eportal_programi",
        "label": "E-portal srednjeĹˇolskih programov (MVI/CPI)",
        "url": "https://eportal.mss.edus.si/msswww/programi2025/programi/NPI/obdelovalec_lesa_glu/kazalo.htm",
        "type": "official_program_catalog",
    },
    {
        "id": "cpi_programi",
        "label": "CPI - izobraĹľevalni programi",
        "url": "https://cpi.si/poklicno-izobrazevanje/izobrazevalni-programi/",
        "type": "official_program_catalog",
    },
]


FALLBACK_THEMES: dict[str, Any] = {
    "osnovna_sola_obvezni_predmeti": [
        "SlovenĹˇÄŤina",
        "Matematika",
        "AngleĹˇÄŤina",
        "Biologija",
        "Kemija",
        "Fizika",
        "Naravoslovje",
        "Geografija",
        "Zgodovina",
        "DruĹľba",
        "Likovna umetnost",
        "Glasbena umetnost",
        "Tehnika in tehnologija",
        "Gospodinjstvo",
        "Ĺ port",
        "RaÄŤunalniĹˇtvo",
    ],
    "splosna_matura_predmeti": [
        "AngleĹˇÄŤina",
        "Biologija",
        "Biotehnologija",
        "Ekonomija",
        "Elektrotehnika",
        "Filozofija",
        "Fizika",
        "FrancoĹˇÄŤina",
        "Geografija",
        "Glasba",
        "GrĹˇÄŤina",
        "Informatika",
        "ItalijanĹˇÄŤina kot drugi jezik",
        "ItalijanĹˇÄŤina kot materinĹˇÄŤina",
        "ItalijanĹˇÄŤina kot tuji jezik",
        "Kemija",
        "LatinĹˇÄŤina",
        "Likovna teorija",
        "MadĹľarĹˇÄŤina kot drugi jezik",
        "MadĹľarĹˇÄŤina kot materinĹˇÄŤina",
        "Matematika",
        "Materiali",
        "Mehanika",
        "NemĹˇÄŤina",
        "Psihologija",
        "RaÄŤunalniĹˇtvo",
        "RuĹˇÄŤina",
        "SlovenĹˇÄŤina",
        "Sociologija",
        "Ĺ panĹˇÄŤina",
        "Umetnostna zgodovina",
        "Zgodovina",
    ],
    "poklicna_matura_prvi_predmet": ["SlovenĹˇÄŤina", "ItalijanĹˇÄŤina", "MadĹľarĹˇÄŤina"],
    "poklicna_matura_drugi_predmet": [
        "Avtomehatronika",
        "Elektrotehnika",
        "Farmacija",
        "Frizerstvo",
        "Gastronomija in turistiÄŤne storitve",
        "Gastronomija in turizem s podjetniĹˇtvom",
        "Gospodarstvo",
        "Graditev objektov",
        "Kemija",
        "Kmetijstvo",
        "Kozmetika",
        "Logistika",
        "Mehatronika",
        "Naravovarstvo",
        "RaÄŤunalniĹˇtvo",
        "StrojniĹˇtvo",
        "Veterinarstvo",
        "Vzgoja predĹˇolskega otroka",
        "Zdravstvena nega",
        "Ĺ˝ivilstvo in prehrana",
    ],
    "poklicna_matura_tretji_predmet": [
        "AngleĹˇÄŤina",
        "ItalijanĹˇÄŤina kot tuji in drugi jezik",
        "Matematika",
        "NemĹˇÄŤina",
        "SlovenĹˇÄŤina kot drugi jezik",
    ],
}

LEVEL2_OVERRIDES: dict[str, list[str]] = {
    "Biologija": [
        "celica",
        "celicno dihanje",
        "fotosinteza",
        "genetika",
        "evolucija",
        "ekologija",
        "clovesko telo",
        "rastline",
        "mikroorganizmi",
        "ekosistemi",
    ],
    "Kemija": [
        "atom in periodni sistem",
        "kemijske vezi",
        "kemijske reakcije",
        "stehiometrija",
        "kisline in baze",
        "redoks reakcije",
        "organska kemija",
        "ogljikovodiki",
        "alkoholi in kisline",
        "polimeri",
    ],
    "Fizika": [
        "gibanje in sila",
        "newtonovi zakoni",
        "energija in delo",
        "toplota",
        "valovanje",
        "optika",
        "elektrika",
        "magnetizem",
        "atom in jedro",
        "sodobna fizika",
    ],
    "Matematika": [
        "stevila in operacije",
        "izrazi in enacbe",
        "linearne funkcije",
        "kvadratne funkcije",
        "geometrija",
        "trigonometrija",
        "odvodi",
        "integrali",
        "zaporedja",
        "verjetnost in statistika",
    ],
    "Geografija": [
        "zemljevid in orientacija",
        "podnebje",
        "prebivalstvo",
        "naselja",
        "gospodarstvo",
        "slovenija",
        "evropa",
        "svet",
        "trajnostni razvoj",
        "naravne nesrece",
    ],
    "Zgodovina": [
        "prazgodovina",
        "stari vek",
        "srednji vek",
        "novi vek",
        "razsvetljenstvo",
        "industrijska revolucija",
        "prva svetovna vojna",
        "druga svetovna vojna",
        "slovenci v 20. stoletju",
        "sodobni svet",
    ],
    "SlovenĹˇÄŤina": [
        "slovnica",
        "pravopis",
        "besedne vrste",
        "skladnja",
        "knjizevnost",
        "interpretacija besedila",
        "esej",
        "povzetek in obnova",
        "retorika",
        "bralna pismenost",
    ],
    "AngleĹˇÄŤina": [
        "slovnica",
        "besedisce",
        "bralno razumevanje",
        "slusno razumevanje",
        "pisanje",
        "govor",
        "casi",
        "pogojni stavki",
        "modalni glagoli",
        "fraze in idiomi",
    ],
}

LEVEL2_CATEGORY_TOPICS: dict[str, list[str]] = {
    "language": [
        "slovnica",
        "pravopis",
        "besedisce",
        "bralno razumevanje",
        "slusno razumevanje",
        "pisno sporocanje",
        "govorno sporocanje",
        "besedilne vrste",
        "argumentacija",
        "jezik v rabi",
        "retorika",
        "interpretacija besedila",
        "analiza napak",
        "vaje za maturo",
        "ponovitev kljucnih pravil",
    ],
    "math": [
        "stevila in operacije",
        "izrazi in enacbe",
        "linearne funkcije",
        "kvadratne funkcije",
        "potence in koreni",
        "logaritmi",
        "geometrija v ravnini",
        "prostorska geometrija",
        "trigonometrija",
        "zaporedja in vrste",
        "odvodi",
        "integrali",
        "kombinatorika",
        "verjetnost",
        "statistika",
    ],
    "biology": [
        "celica",
        "celicno dihanje",
        "fotosinteza",
        "biomolekule",
        "genetika",
        "evolucija",
        "ekologija",
        "ekosistemi",
        "mikroorganizmi",
        "clovesko telo",
        "rastline",
        "zivali",
        "homeostaza",
        "dedovanje",
        "biotehnologija",
    ],
    "chemistry": [
        "atom in periodni sistem",
        "kemijske vezi",
        "molekule in spojine",
        "stehiometrija",
        "kemijske reakcije",
        "kisline in baze",
        "redoks reakcije",
        "raztopine",
        "ravnotezje",
        "organska kemija",
        "ogljikovodiki",
        "alkoholi in kisline",
        "polimeri",
        "elektrokemija",
        "laboratorijske metode",
    ],
    "physics": [
        "gibanje in sila",
        "newtonovi zakoni",
        "energija in delo",
        "impulz in gibalna kolicina",
        "gravitacija",
        "tlak in hidrodinamika",
        "toplota",
        "termodinamika",
        "valovanje",
        "optika",
        "elektrika",
        "magnetizem",
        "nihanje",
        "atom in jedro",
        "sodobna fizika",
    ],
    "history": [
        "prazgodovina",
        "stari vek",
        "srednji vek",
        "novi vek",
        "razsvetljenstvo",
        "industrijska revolucija",
        "19. stoletje",
        "prva svetovna vojna",
        "medvojno obdobje",
        "druga svetovna vojna",
        "hladna vojna",
        "slovenci v 20. stoletju",
        "sodobni svet",
        "zgodovinski viri",
        "vzrok in posledica",
    ],
    "geography": [
        "kartografija",
        "zemljevid in orientacija",
        "podnebje",
        "vreme in podnebni procesi",
        "prebivalstvo",
        "poselitev",
        "naselja",
        "gospodarstvo",
        "promet",
        "slovenija",
        "evropa",
        "svet",
        "trajnostni razvoj",
        "okoljski problemi",
        "naravne nesrece",
    ],
    "computer_science": [
        "osnove racunalnistva",
        "algoritmi",
        "programiranje",
        "podatkovne strukture",
        "baze podatkov",
        "racunalniska omrezja",
        "internetni protokoli",
        "operacijski sistemi",
        "kibernetska varnost",
        "kriptografija",
        "spletne tehnologije",
        "razvoj programske opreme",
        "testiranje",
        "umetna inteligenca",
        "etika v IT",
    ],
    "social_science": [
        "osnovni pojmi",
        "metode raziskovanja",
        "druzbene strukture",
        "institucije",
        "kultura",
        "identiteta",
        "druzbene spremembe",
        "moc in oblast",
        "norme in vrednote",
        "globalizacija",
        "aktualni primeri",
        "analiza virov",
        "primerjalni pristop",
        "argumentacija",
        "uporaba teorije",
    ],
    "economics_business": [
        "osnovni ekonomski pojmi",
        "ponudba in povprasevanje",
        "trg in konkurenca",
        "gospodarska rast",
        "inflacija",
        "brezposelnost",
        "denar in banke",
        "fiskalna politika",
        "mednarodna menjava",
        "podjetnistvo",
        "racunovodstvo osnove",
        "marketing",
        "menedzment",
        "poslovni modeli",
        "analiza primera",
    ],
    "philosophy": [
        "uvod v filozofijo",
        "logika",
        "spoznavna teorija",
        "ontologija",
        "etika",
        "politicna filozofija",
        "estetika",
        "filozofija znanosti",
        "antiÄŤna filozofija",
        "novoveska filozofija",
        "moderna filozofija",
        "argumentacija",
        "miselni poskusi",
        "primerjava avtorjev",
        "kriticna presoja",
    ],
    "arts": [
        "osnovni pojmi stroke",
        "zgodovinski razvoj",
        "slogi in smeri",
        "analiza dela",
        "kompozicija",
        "izrazna sredstva",
        "avtorji in dela",
        "tehnike in materiali",
        "kultura in druzba",
        "sodobne prakse",
        "interpretacija",
        "primerjalna analiza",
        "terminologija",
        "projektna naloga",
        "portfolio in refleksija",
    ],
    "engineering": [
        "tehniski sistemi",
        "materiali",
        "meritve in tolerance",
        "tehniska dokumentacija",
        "nacrti in skice",
        "konstrukcije",
        "vzdrzevanje",
        "varnost pri delu",
        "kakovost",
        "procesi izdelave",
        "diagnostika napak",
        "optimizacija procesa",
        "normativi",
        "strokovni izracuni",
        "primeri iz prakse",
    ],
    "vocational": [
        "osnove stroke",
        "orodja in oprema",
        "postopki dela",
        "strokovna terminologija",
        "kakovost storitve",
        "varnost in higiena",
        "komunikacija s strankami",
        "zakonski okviri",
        "dokumentacija",
        "strokovni izracuni",
        "prakticni primeri",
        "resitev pogostih napak",
        "organizacija dela",
        "trajnostni vidiki",
        "priprava na izpit",
    ],
    "sports": [
        "gibalne sposobnosti",
        "kondicijska priprava",
        "tehnika gibanja",
        "taktika",
        "zdrav nacin zivljenja",
        "prehrana",
        "preprecevanje poskodb",
        "fair play",
        "pravila sportov",
        "samovrednotenje napredka",
    ],
}

SUBJECT_CATEGORY_MAP: dict[str, str] = {
    "SlovenĹˇÄŤina": "language",
    "AngleĹˇÄŤina": "language",
    "NemĹˇÄŤina": "language",
    "FrancoĹˇÄŤina": "language",
    "ItalijanĹˇÄŤina": "language",
    "ItalijanĹˇÄŤina kot drugi jezik": "language",
    "ItalijanĹˇÄŤina kot materinĹˇÄŤina": "language",
    "ItalijanĹˇÄŤina kot tuji jezik": "language",
    "ItalijanĹˇÄŤina kot tuji in drugi jezik": "language",
    "MadĹľarĹˇÄŤina": "language",
    "MadĹľarĹˇÄŤina kot drugi jezik": "language",
    "MadĹľarĹˇÄŤina kot materinĹˇÄŤina": "language",
    "RuĹˇÄŤina": "language",
    "Ĺ panĹˇÄŤina": "language",
    "SlovenĹˇÄŤina kot drugi jezik": "language",
    "Matematika": "math",
    "Biologija": "biology",
    "Biotehnologija": "biology",
    "Kemija": "chemistry",
    "Fizika": "physics",
    "Geografija": "geography",
    "Zgodovina": "history",
    "Psihologija": "social_science",
    "Sociologija": "social_science",
    "DruĹľba": "social_science",
    "Filozofija": "philosophy",
    "Ekonomija": "economics_business",
    "Gospodarstvo": "economics_business",
    "Informatika": "computer_science",
    "RaÄŤunalniĹˇtvo": "computer_science",
    "Elektrotehnika": "engineering",
    "Mehanika": "engineering",
    "Materiali": "engineering",
    "StrojniĹˇtvo": "engineering",
    "Graditev objektov": "engineering",
    "Avtomehatronika": "engineering",
    "Mehatronika": "engineering",
    "Likovna umetnost": "arts",
    "Likovna teorija": "arts",
    "Glasba": "arts",
    "Glasbena umetnost": "arts",
    "Umetnostna zgodovina": "arts",
    "LatinĹˇÄŤina": "language",
    "GrĹˇÄŤina": "language",
    "Naravoslovje": "biology",
    "Tehnika in tehnologija": "engineering",
    "Gospodinjstvo": "vocational",
    "Ĺ port": "sports",
    "Farmacija": "vocational",
    "Frizerstvo": "vocational",
    "Gastronomija in turistiÄŤne storitve": "vocational",
    "Gastronomija in turizem s podjetniĹˇtvom": "vocational",
    "Kmetijstvo": "vocational",
    "Kozmetika": "vocational",
    "Logistika": "vocational",
    "Naravovarstvo": "vocational",
    "Veterinarstvo": "vocational",
    "Vzgoja predĹˇolskega otroka": "vocational",
    "Zdravstvena nega": "vocational",
    "Ĺ˝ivilstvo in prehrana": "vocational",
}


class AnchorCollector(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._in_a = False
        self._href = ""
        self._text_parts: list[str] = []
        self.anchors: list[tuple[str, str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() != "a":
            return
        self._in_a = True
        self._href = dict(attrs).get("href") or ""
        self._text_parts = []

    def handle_data(self, data: str) -> None:
        if self._in_a:
            self._text_parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() != "a" or not self._in_a:
            return
        text = normalize_space("".join(self._text_parts))
        self.anchors.append((self._href, text))
        self._in_a = False
        self._href = ""
        self._text_parts = []


def normalize_space(text: str) -> str:
    return re.sub(r"\s+", " ", unescape(text or "")).strip()


def fetch_html(url: str, timeout: int = 20) -> str:
    req = Request(url, headers={"User-Agent": "mentor-themes-db/1.0"})
    with urlopen(req, timeout=timeout) as resp:
        raw = resp.read()
        charset = resp.headers.get_content_charset() or "utf-8"
    return raw.decode(charset, errors="replace")


def clean_theme_label(text: str) -> str:
    t = normalize_space(text)
    t = re.sub(r"\s*\(pdf[^)]*\)\s*$", "", t, flags=re.IGNORECASE)
    t = re.sub(r"\s*\(v uporabi od[^)]*\)\s*$", "", t, flags=re.IGNORECASE)
    t = re.sub(r"\s+[-â€“]\s+.*$", "", t)
    return t.strip(" -")


def unique_preserve(items: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for item in items:
        key = item.casefold()
        if not item or key in seen:
            continue
        seen.add(key)
        out.append(item)
    return out


def _norm_match(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text.casefold())
    normalized = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    normalized = re.sub(r"[^a-z0-9\s]+", " ", normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized


def _looks_like_theme_candidate(text: str) -> bool:
    t = normalize_space(text)
    if not t:
        return False
    if len(t) < 3 or len(t) > 140:
        return False
    low = t.casefold()
    banned_fragments = (
        "piĹˇkot",
        "cookie",
        "prijava",
        "odjava",
        "navigacija",
        "menu",
        "kontakt",
        "novica",
        "domov",
        "veÄŤ",
        "preberi",
        "nazaj",
        "iskanje",
        "search",
        "facebook",
        "instagram",
        "youtube",
        "linkedin",
        "copyright",
        "varstvo osebnih podatkov",
        "uradni list",
        "ctrl+u",
        "ctrl u",
    )
    if any(fragment in low for fragment in banned_fragments):
        return False
    # Ignore keyboard shortcuts / devtool hints.
    if re.search(r"\bctrl\s*\+?\s*[a-z]\b", low):
        return False
    if re.search(r"\balt\s*\+?\s*[a-z]\b", low):
        return False
    if re.search(r"\bshift\s*\+?\s*[a-z]\b", low):
        return False
    # Ignore legal/meta references that are not themes.
    if re.search(r"\buradni\s+list\b", low):
        return False
    # Reject mostly punctuation/numeric rows.
    alpha = sum(ch.isalpha() for ch in t)
    if alpha < 3:
        return False
    return True


def extract_all_official_candidates(html: str, base_url: str) -> list[str]:
    anchors = AnchorCollector()
    anchors.feed(html)
    out: list[str] = []
    for href, text in anchors.anchors:
        if not href:
            continue
        full = urljoin(base_url, href)
        label = clean_theme_label(text)
        if not _looks_like_theme_candidate(label):
            continue
        if full.lower().endswith(".pdf") or any(
            key in full for key in ("/predmeti/", "/programi", "/ucni", "/katalog", "/poklici")
        ):
            out.append(label)
    return _final_theme_cleanup(out)


def _extract_program_titles(html: str, base_url: str) -> list[str]:
    anchors = AnchorCollector()
    anchors.feed(html)
    out: list[str] = []
    for href, text in anchors.anchors:
        if not href:
            continue
        full = urljoin(base_url, href)
        label = clean_theme_label(text)
        low = label.casefold()
        if not _looks_like_theme_candidate(label):
            continue
        if any(x in low for x in ("programi", "katalog", "izobrazevalni programi", "teme")):
            continue
        if any(x in full for x in ("/programi", "/poklic", "/predmeti", "/matura")):
            out.append(label)
    return _final_theme_cleanup(out)


def _final_theme_cleanup(items: list[str]) -> list[str]:
    cleaned: list[str] = []
    banned = (
        "uradni list",
        "ctrl+u",
        "ctrl u",
        "poklicna matura",
        "splosna matura",
        "programi in",
        "srednjesolski",
        "skoci na vsebino",
        "k vsebini",
        "splosni del",
        "posebni del",
        "podporno gradivo",
        "interesne dejavnosti",
        "dnevi dejavnosti",
        "koncept ",
        "navodila",
        "raziskave in",
        "kakovost psi",
        "prakticno izobrazevanje",
        "zakljucevanje izobrazevanja",
        "izobrazevanje in usposabljanje",
        "podpora izobrazevanju",
        "ucbeniki in ucna tehnologija",
        "vkljucujoce psi",
        "o poklicnem in strokovnem izobrazevanju",
        "poklicno izobrazevanje",
        "srednje poklicno izobrazevanje",
        "srednje strokovno izobrazevanje",
        "poklicno tehnisko izobrazevanje",
        "visjesolsko strokovno izobrazevanje",
        "izpopolnjevanje na podrocju",
    )
    for item in items:
        low_ascii = _norm_match(item)
        if any(b in low_ascii for b in banned):
            continue
        if re.search(r"\(\s*uradni\s+list", low_ascii):
            continue
        if re.search(r"^\d+_", item):
            continue
        if "?" in item:
            continue
        cleaned.append(item)
    return unique_preserve(cleaned)


def _category_for_subject(subject: str) -> str:
    if subject in SUBJECT_CATEGORY_MAP:
        return SUBJECT_CATEGORY_MAP[subject]
    lower = subject.casefold()
    if "jezik" in lower:
        return "language"
    if "raÄŤunal" in lower or "racunal" in lower or "informat" in lower:
        return "computer_science"
    if "Ĺˇport" in lower or "sport" in lower:
        return "sports"
    if "teh" in lower or "stroj" in lower or "elektro" in lower or "grad" in lower:
        return "engineering"
    return "vocational"


def build_level2_map(themes: dict[str, list[str]]) -> dict[str, list[str]]:
    subjects: list[str] = []
    for items in themes.values():
        subjects.extend(items)
    subjects = unique_preserve(subjects)

    out: dict[str, list[str]] = {}
    for subject in subjects:
        if subject in LEVEL2_OVERRIDES:
            out[subject] = unique_preserve(LEVEL2_OVERRIDES[subject])
            continue
        category = _category_for_subject(subject)
        base = LEVEL2_CATEGORY_TOPICS.get(category, LEVEL2_CATEGORY_TOPICS["vocational"])
        out[subject] = unique_preserve(base)
    return out


def extract_os_themes(html: str, base_url: str) -> list[str]:
    collector = AnchorCollector()
    collector.feed(html)
    out: list[str] = []
    for href, text in collector.anchors:
        full = urljoin(base_url, href)
        if not full.lower().endswith(".pdf"):
            continue
        label = clean_theme_label(text)
        if not label:
            continue
        if any(
            x in label.casefold()
            for x in ("didakti", "priporoÄŤ", "predmetnik", "smernice", "strateg", "kurikulum")
        ):
            continue
        if len(label) > 120:
            continue
        out.append(label)
    return _final_theme_cleanup(out)


def extract_splosna_matura_subjects(html: str, base_url: str) -> list[str]:
    collector = AnchorCollector()
    collector.feed(html)
    out: list[str] = []
    for href, text in collector.anchors:
        full = urljoin(base_url, href)
        path = urlparse(full).path.strip("/").split("/")
        if len(path) != 3:
            continue
        if path[0] != "splosna-matura" or path[1] != "predmeti":
            continue
        label = clean_theme_label(text)
        if label.casefold() in {"predmeti", "nazaj"}:
            continue
        if label:
            out.append(label)
    return _final_theme_cleanup(out)


@dataclass
class PoklicnaSubjects:
    prvi: list[str]
    drugi: list[str]
    tretji: list[str]


def extract_poklicna_matura_subjects(html: str, base_url: str) -> PoklicnaSubjects:
    collector = AnchorCollector()
    collector.feed(html)
    prvi: list[str] = []
    drugi: list[str] = []
    tretji: list[str] = []
    for href, text in collector.anchors:
        full = urljoin(base_url, href)
        path = urlparse(full).path.strip("/").split("/")
        if len(path) != 4:
            continue
        if path[0] != "poklicna-matura" or path[1] != "predmeti":
            continue
        bucket = path[2]
        label = clean_theme_label(text)
        if not label or label.casefold() in {"predmeti", "nazaj"}:
            continue
        if bucket == "prvi-predmet":
            prvi.append(label)
        elif bucket == "drugi-predmet":
            drugi.append(label)
        elif bucket == "tretji-predmet":
            tretji.append(label)
    return PoklicnaSubjects(
        prvi=_final_theme_cleanup(prvi),
        drugi=_final_theme_cleanup(drugi),
        tretji=_final_theme_cleanup(tretji),
    )


def build_database(no_fetch: bool = False, official_only: bool = False) -> dict[str, Any]:
    fetched: dict[str, str] = {}
    errors: dict[str, str] = {}
    official_by_source: dict[str, list[str]] = {}

    if not no_fetch:
        for src in SOURCES:
            try:
                html = fetch_html(src["url"])
                fetched[src["id"]] = html
                if src["id"] == "gov_os":
                    official_by_source[src["id"]] = extract_os_themes(html, src["url"])
                elif src["id"] == "ric_sm_predmeti":
                    official_by_source[src["id"]] = extract_splosna_matura_subjects(html, src["url"])
                elif src["id"] == "ric_pm_predmeti":
                    pm_items = extract_poklicna_matura_subjects(html, src["url"])
                    official_by_source[src["id"]] = unique_preserve(pm_items.prvi + pm_items.drugi + pm_items.tretji)
                elif src["id"] in {"gov_srednjesolski_programi", "eportal_programi", "cpi_programi"}:
                    official_by_source[src["id"]] = _extract_program_titles(html, src["url"])
                else:
                    official_by_source[src["id"]] = extract_all_official_candidates(html, src["url"])
            except URLError as exc:
                errors[src["id"]] = str(exc)
            except Exception as exc:  # pragma: no cover - best-effort tooling
                errors[src["id"]] = f"{type(exc).__name__}: {exc}"

    os_themes = FALLBACK_THEMES["osnovna_sola_obvezni_predmeti"]
    if "gov_os" in fetched:
        parsed = extract_os_themes(fetched["gov_os"], next(x["url"] for x in SOURCES if x["id"] == "gov_os"))
        if parsed:
            os_themes = parsed

    sm_themes = FALLBACK_THEMES["splosna_matura_predmeti"]
    if "ric_sm_predmeti" in fetched:
        parsed = extract_splosna_matura_subjects(
            fetched["ric_sm_predmeti"], next(x["url"] for x in SOURCES if x["id"] == "ric_sm_predmeti")
        )
        if parsed:
            sm_themes = parsed

    pm = PoklicnaSubjects(
        prvi=FALLBACK_THEMES["poklicna_matura_prvi_predmet"],
        drugi=FALLBACK_THEMES["poklicna_matura_drugi_predmet"],
        tretji=FALLBACK_THEMES["poklicna_matura_tretji_predmet"],
    )
    if "ric_pm_predmeti" in fetched:
        parsed = extract_poklicna_matura_subjects(
            fetched["ric_pm_predmeti"], next(x["url"] for x in SOURCES if x["id"] == "ric_pm_predmeti")
        )
        if parsed.prvi:
            pm.prvi = parsed.prvi
        if parsed.drugi:
            pm.drugi = parsed.drugi
        if parsed.tretji:
            pm.tretji = parsed.tretji

    themes = {
        "osnovna_sola_obvezni_predmeti": os_themes,
        "splosna_matura_predmeti": sm_themes,
        "poklicna_matura_prvi_predmet": pm.prvi,
        "poklicna_matura_drugi_predmet": pm.drugi,
        "poklicna_matura_tretji_predmet": pm.tretji,
    }
    themes_level2 = build_level2_map(themes)
    official_union: list[str] = []
    for src in SOURCES:
        official_union.extend(official_by_source.get(src["id"], []))
    official_union = unique_preserve(official_union)
    if official_only:
        official_bucket = official_union if official_union else unique_preserve(
            [item for group in themes.values() for item in group]
        )
        themes = {"official_all": official_bucket}
        themes_level2 = {}

    return {
        "schema_version": 1,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "generator": "scripts/regenerate_themes_db.py",
        "source_urls": SOURCES,
        "fetch_errors": errors,
        "themes": themes,
        "themes_level2": themes_level2,
        "themes_official_all": {
            "count": len(official_union),
            "by_source": official_by_source,
            "all": official_union,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Regenerate themes database from official sources.")
    parser.add_argument("--output", type=Path, default=OUTPUT_PATH, help="Output JSON path.")
    parser.add_argument(
        "--no-fetch",
        action="store_true",
        help="Use fallback curated data only (no network requests).",
    )
    parser.add_argument(
        "--official-only",
        action="store_true",
        help="Store only themes discovered from official sources (single 'official_all' bucket).",
    )
    args = parser.parse_args()

    db = build_database(no_fetch=args.no_fetch, official_only=args.official_only)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(db, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote: {args.output}")


if __name__ == "__main__":
    main()


