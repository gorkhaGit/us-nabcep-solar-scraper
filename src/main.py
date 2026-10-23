from __future__ import annotations

import asyncio
import html
import json
import re
from typing import Any
from urllib.parse import urlencode

import httpx
from apify import Actor

DIRECTORY_URL = "https://directories.nabcep.org/"
ACCREDITED_URL = "https://www.nabcep.org/accredited/"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}


def clean_str(raw: str | None) -> str:
    if not raw:
        return ""
    text = html.unescape(raw).replace("\xa0", " ")
    text = re.sub(r"<[^>]+>", " ", text)
    return " ".join(text.split()).strip()


def normalize_url(raw_url: str | None) -> str:
    if not raw_url:
        return ""
    u = html.unescape(raw_url).strip()
    if u in ("", "//", "http://", "https://", "#"):
        return ""
    if u.startswith("//"):
        return f"https:{u}"
    if not u.startswith(("http://", "https://")):
        return f"https://{u.lstrip('/')}"
    return u


def parse_city_state_zip(loc: str) -> tuple[str, str, str]:
    loc = loc.strip()
    if not loc:
        return "", "", ""
    m = re.match(
        r"^(.*?)(?:,\s*|\s+)([A-Za-z]{2})\s+(\d{5}(?:-\d{4})?|[A-Za-z]\d[A-Za-z]\s*\d[A-Za-z]\d)?$",
        loc,
    )
    if m:
        return m.group(1).strip(" ,"), m.group(2).upper(), (m.group(3) or "").strip()
    if "," in loc:
        parts = [p.strip() for p in loc.split(",", 1)]
        return parts[0], parts[1], ""
    return loc, "", ""


def parse_accredited_companies(page_html: str, state_filter: str = "") -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    start_idx = page_html.find("NABCEP Company Accreditation")
    if start_idx == -1:
        return results

    # Slice strictly inside the accreditation content column
    chunk = page_html[start_idx:]
    end_idx = chunk.find("<!-- .entry-content")
    if end_idx != -1:
        chunk = chunk[:end_idx]

    # Split by <h2>State</h2> sections
    h2_sections = re.split(r"<h2[^>]*>(.*?)</h2>", chunk, flags=re.S | re.I)
    # h2_sections[0] is intro before first <h2>; then pairs of (state_name, state_html)
    for idx in range(1, len(h2_sections), 2):
        current_state = clean_str(h2_sections[idx])
        state_html = h2_sections[idx + 1] if idx + 1 < len(h2_sections) else ""

        h4_blocks = re.split(r"<h4[^>]*>(.*?)</h4>", state_html, flags=re.S | re.I)
        for j in range(1, len(h4_blocks), 2):
            company_name = clean_str(h4_blocks[j])
            details_html = h4_blocks[j + 1] if j + 1 < len(h4_blocks) else ""
            if not company_name or not details_html:
                continue

            p_matches = re.findall(r"<p[^>]*>(.*?)</p>", details_html, flags=re.S | re.I)
            combined_p = "<br />".join(p_matches) if p_matches else details_html

            href_m = re.search(r'href=["\']([^"\']+)["\']', combined_p, re.I)
            website = normalize_url(href_m.group(1) if href_m else "")

            lines = [clean_str(line) for line in re.split(r"<br\s*/?>|\n", combined_p, flags=re.I)]
            lines = [ln for ln in lines if ln and ln.lower() != "website"]
            if not lines:
                continue

            decision_maker = lines[0] if len(lines) >= 1 else ""
            street_address = lines[1] if len(lines) >= 2 else ""
            city_state_line = lines[2] if len(lines) >= 3 else ""
            city, state_code, postal_code = parse_city_state_zip(city_state_line)

            if state_filter:
                sf = state_filter.strip().lower()
                if sf not in current_state.lower() and sf != state_code.lower():
                    continue

            results.append({
                "record_type": "accredited_company",
                "name": decision_maker,
                "company": company_name,
                "website": website,
                "certification_tier": "NABCEP Accredited Company",
                "primary_certification": "NABCEP Company Accreditation",
                "primary_cert_number": "",
                "primary_cert_expires": "",
                "certifications": [
                    {
                        "title": "NABCEP Company Accreditation",
                        "cert_number": "",
                        "expires": "",
                    }
                ],
                "street_address": street_address,
                "city": city,
                "state": state_code or current_state,
                "state_full": current_state,
                "postal_code": postal_code,
                "country": "USA",
                "location_raw": city_state_line,
                "is_veteran": False,
                "candidate_id": "",
                "contact_form_url": "",
                "source_url": ACCREDITED_URL,
            })

    return results


def parse_directory_cards(page_html: str) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    cards = re.split(r'<div class="card directory-card', page_html)[1:]

    for card in cards:
        name_m = re.search(r'class="directory-card__name"[^>]*>(.*?)</h5>', card, re.S)
        raw_name_html = name_m.group(1) if name_m else ""
        is_veteran = "usa-flag" in raw_name_html.lower()
        name = clean_str(raw_name_html)
        if not name:
            continue

        certs: list[dict[str, str]] = []
        cert_blocks = re.findall(
            r'<h5 class="mb-0">(.*?)</h5>\s*<p class="mb-0">Cert #:\s*(.*?)</p>\s*<p class="mb-0">Expires:\s*(.*?)</p>',
            card,
            re.S,
        )
        for c_title, c_num, c_exp in cert_blocks:
            certs.append({
                "title": clean_str(c_title),
                "cert_number": clean_str(c_num),
                "expires": clean_str(c_exp),
            })

        primary_cert = certs[0]["title"] if certs else ""
        primary_num = certs[0]["cert_number"] if certs else ""
        primary_exp = certs[0]["expires"] if certs else ""
        tier = (
            "Associate"
            if "associate" in primary_cert.lower() or primary_num.startswith("PVA-")
            else "Board Certified Professional"
        )

        company = ""
        website = ""
        country = ""
        location_raw = ""

        info_m = re.search(r'<div class="directory-card__info">(.*?)</div>', card, re.S)
        if info_m:
            info_html = info_m.group(1)
            p_tags = re.findall(r'<p class="card-text">(.*?)</p>', info_html, re.S)
            for idx, p_inner in enumerate(p_tags):
                txt = clean_str(p_inner)
                if txt.startswith("Country:"):
                    country = txt.replace("Country:", "", 1).strip()
                elif txt.startswith("Location:"):
                    location_raw = txt.replace("Location:", "", 1).strip()
                elif "<a " in p_inner:
                    href_m = re.search(r'href=["\']([^"\']+)["\']', p_inner, re.I)
                    website = normalize_url(href_m.group(1) if href_m else "")
                elif idx == 0 and txt:
                    company = txt

        city, state_code, postal_code = parse_city_state_zip(location_raw)

        cand_m = re.search(r"candidate_id=(\d+)", card)
        candidate_id = cand_m.group(1) if cand_m else ""
        contact_url = (
            f"https://directories.nabcep.org/wp-admin/admin-ajax.php?action=ci_nabcep_contact_form&candidate_id={candidate_id}"
            if candidate_id
            else ""
        )

        records.append({
            "record_type": "certified_directory_member",
            "name": name,
            "company": company,
            "website": website,
            "certification_tier": tier,
            "primary_certification": primary_cert,
            "primary_cert_number": primary_num,
            "primary_cert_expires": primary_exp,
            "certifications": certs,
            "street_address": "",
            "city": city,
            "state": state_code,
            "state_full": "",
            "postal_code": postal_code,
            "country": country,
            "location_raw": location_raw,
            "is_veteran": is_veteran,
            "candidate_id": candidate_id,
            "contact_form_url": contact_url,
            "source_url": DIRECTORY_URL,
        })

    return records


def build_query_params(
    page: int,
    cert_type: str,
    country: str,
    state: str,
    search_query: str,
) -> dict[str, str]:
    params: dict[str, str] = {}
    if cert_type in ("professional", "associate"):
        params["_certtypes"] = cert_type
    if country.strip():
        params["_countries"] = country.strip().lower()
    if state.strip():
        params["_states"] = state.strip()
    if search_query.strip():
        params["_searcher"] = search_query.strip()
    if page > 1:
        params["_paged"] = str(page)
    return params


async def push_and_charge(items: list[dict[str, Any]]) -> None:
    if not items:
        return
    await Actor.push_data(items)
    try:
        await Actor.charge(event_name="lead-scraped", count=len(items))
    except Exception:
        pass


async def main() -> None:
    async with Actor:
        actor_input = await Actor.get_input() or {}
        include_accredited = bool(actor_input.get("includeAccreditedCompanies", True))
        cert_type = str(actor_input.get("certType", "all")).lower()
        country = str(actor_input.get("country", "")).strip()
        state = str(actor_input.get("state", "")).strip()
        search_query = str(actor_input.get("searchQuery", "")).strip()
        only_with_company = bool(actor_input.get("onlyWithCompanyOrWebsite", False))
        max_items = int(actor_input.get("maxItems", 100))
        concurrency = max(1, min(10, int(actor_input.get("concurrency", 5))))

        proxy_cfg = actor_input.get("proxyConfiguration")
        proxy_url: str | None = None
        if proxy_cfg and (proxy_cfg.get("useApifyProxy") or proxy_cfg.get("proxyUrls")):
            proxy_configuration = await Actor.create_proxy_configuration(actor_proxy_input=proxy_cfg)
            if proxy_configuration:
                proxy_url = await proxy_configuration.new_url()

        total_pushed = 0

        async with httpx.AsyncClient(
            headers=HEADERS,
            proxy=proxy_url,
            follow_redirects=True,
            timeout=30.0,
        ) as client:
            if include_accredited:
                Actor.log.info("Fetching NABCEP Accredited Solar Companies (CEO/Owner directory)...")
                try:
                    acc_resp = await client.get(ACCREDITED_URL)
                    if acc_resp.status_code == 200:
                        acc_items = parse_accredited_companies(acc_resp.text, state_filter=state)
                        if search_query:
                            sq = search_query.lower()
                            acc_items = [
                                item for item in acc_items
                                if sq in item["company"].lower() or sq in item["name"].lower()
                            ]
                        if max_items > 0:
                            acc_items = acc_items[: max(0, max_items - total_pushed)]
                        if acc_items:
                            await push_and_charge(acc_items)
                            total_pushed += len(acc_items)
                            Actor.log.info(f"Pushed {len(acc_items)} NABCEP Accredited Solar Companies.")
                except Exception as exc:
                    Actor.log.warning(f"Failed to fetch accredited companies: {exc}")

            if max_items > 0 and total_pushed >= max_items:
                Actor.log.info(f"Reached maxItems ({max_items}). Finished.")
                return

            p1_params = build_query_params(1, cert_type, country, state, search_query)
            p1_url = f"{DIRECTORY_URL}?{urlencode(p1_params)}" if p1_params else DIRECTORY_URL
            Actor.log.info(f"Fetching Directory Page 1: {p1_url}")

            r1 = await client.get(p1_url)
            r1.raise_for_status()

            total_pages = 1
            total_rows = 0
            fwp_m = re.search(r"FWP_JSON\s*=\s*(\{.*?\});\s*</script>", r1.text, re.S) or re.search(
                r"FWP_JSON\s*=\s*(\{.*?\});\n", r1.text, re.S
            )
            if fwp_m:
                try:
                    fwp = json.loads(fwp_m.group(1))
                    pager = fwp.get("preload_data", {}).get("settings", {}).get("pager", {})
                    total_pages = int(pager.get("total_pages", 1))
                    total_rows = int(pager.get("total_rows", 0))
                except Exception:
                    pass

            Actor.log.info(f"Directory matched {total_rows} solar professionals across {total_pages} pages.")

            def filter_cards(cards: list[dict[str, Any]]) -> list[dict[str, Any]]:
                if not only_with_company:
                    return cards
                return [c for c in cards if c.get("company") or c.get("website")]

            p1_cards = filter_cards(parse_directory_cards(r1.text))
            if max_items > 0:
                p1_cards = p1_cards[: max(0, max_items - total_pushed)]
            if p1_cards:
                await push_and_charge(p1_cards)
                total_pushed += len(p1_cards)
                Actor.log.info(f"Page 1/{total_pages}: Pushed {len(p1_cards)} records (Total: {total_pushed})")

            if total_pages <= 1 or (max_items > 0 and total_pushed >= max_items):
                Actor.log.info(f"Scraping complete! Total records pushed: {total_pushed}")
                return

            sem = asyncio.Semaphore(concurrency)

            async def fetch_page(page_num: int) -> list[dict[str, Any]]:
                async with sem:
                    q_params = build_query_params(page_num, cert_type, country, state, search_query)
                    url = f"{DIRECTORY_URL}?{urlencode(q_params)}"
                    for attempt in range(3):
                        try:
                            resp = await client.get(url)
                            if resp.status_code == 200:
                                return filter_cards(parse_directory_cards(resp.text))
                        except Exception as e:
                            if attempt == 2:
                                Actor.log.warning(f"Page {page_num} failed after 3 attempts: {e}")
                        await asyncio.sleep(0.8 * (attempt + 1))
                    return []

            current_page = 2
            batch_size = concurrency * 2
            while current_page <= total_pages:
                if max_items > 0 and total_pushed >= max_items:
                    break
                end_page = min(total_pages, current_page + batch_size - 1)
                pages_to_fetch = list(range(current_page, end_page + 1))

                results_nested = await asyncio.gather(*(fetch_page(p) for p in pages_to_fetch))
                batch_items: list[dict[str, Any]] = []
                for page_items in results_nested:
                    batch_items.extend(page_items)

                if max_items > 0:
                    batch_items = batch_items[: max(0, max_items - total_pushed)]

                if batch_items:
                    await push_and_charge(batch_items)
                    total_pushed += len(batch_items)
                    Actor.log.info(
                        f"Pages {current_page}-{end_page}/{total_pages}: "
                        f"Pushed {len(batch_items)} records (Total: {total_pushed})"
                    )

                current_page = end_page + 1

        Actor.log.info(f"Scraping complete! Total records pushed: {total_pushed}")
