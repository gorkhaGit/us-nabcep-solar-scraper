# US NABCEP Solar Installers & Accredited Companies Scraper

Extract **6,750+ NABCEP Certified Solar Professionals, Associates, and Accredited Solar Installation Companies** directly from the official North American Board of Certified Energy Practitioners registries (`directories.nabcep.org` and `nabcep.org/accredited/`).

Built for **solar equipment wholesalers, B2B SaaS sales teams, clean-energy recruiters, and market researchers** who need verified US & Canadian solar contractor leads without slow browser automation.

---

## What Data Does This Scraper Extract?

1. **NABCEP Accredited Solar Companies (`record_type: "accredited_company"`)**
   - **Company Name & Website URL**
   - **Decision-Maker Name & Title** (CEO, President, Owner, Co-Founder)
   - **Full Street Address, City, State, and Postal Code**
2. **NABCEP Certified Solar Professionals & Associates (`record_type: "certified_directory_member"`)**
   - **Full Name & US Military Veteran Status (`is_veteran`)**
   - **Employer / Solar Company Name & Normalized Website URL**
   - **Certification Tier** (`Board Certified Professional` — 2,673 pros, or `Associate` — 4,078 pros)
   - **All Active Certifications, Cert Numbers (`PVA-...`, `PVIP-...`), and Expiration Dates**
   - **Location (`City`, `State`, `Postal Code`, `Country`) & Direct NABCEP Contact Endpoint**

---

## Key Features

- **Ultra-Fast Lightweight HTTP Architecture:** Uses pure async HTTP requests (`httpx`) with zero headless browser overhead—consumes minimal Apify Compute Units (CUs).
- **B2B Company Filter (`onlyWithCompanyOrWebsite`):** Toggle one checkbox to skip individual technicians without an employer/website and strictly extract B2B solar company leads.
- **Granular Filtering:** Filter by certification tier (`professional` vs `associate`), country (`usa`, `canada`), state (`CA`, `TX`, `FL`, etc.), or keyword.

---

## Sample Output Record

~~~json
{
  "record_type": "certified_directory_member",
  "name": "Darren Aaserude",
  "company": "Power Northwest",
  "website": "https://powernw.com",
  "certification_tier": "Board Certified Professional",
  "primary_certification": "PV Installation Professional (PVIP)",
  "primary_cert_number": "PV-041517-011428",
  "primary_cert_expires": "04-15-2026",
  "certifications": [
    {
      "title": "PV Installation Professional (PVIP)",
      "cert_number": "PV-041517-011428",
      "expires": "04-15-2026"
    }
  ],
  "street_address": "",
  "city": "Portland",
  "state": "OR",
  "state_full": "",
  "postal_code": "97210",
  "country": "USA",
  "location_raw": "Portland, Or 97210",
  "is_veteran": true,
  "candidate_id": "84122",
  "contact_form_url": "https://directories.nabcep.org/wp-admin/admin-ajax.php?action=ci_nabcep_contact_form&candidate_id=84122",
  "source_url": "https://directories.nabcep.org/"
}
~~~

---

## Sample Dataset Downloads (CSV & JSON)

Want to inspect the exact B2B data structure before running the Actor? Check out the live sample exports in this repository:
- **[50 Verified US Solar Companies & Installers (CSV)](./sample_output/nabcep_b2b_sample_50.csv)**
- **[10 Verified US Solar Leads (JSON)](./sample_output/nabcep_b2b_sample_10.json)**
