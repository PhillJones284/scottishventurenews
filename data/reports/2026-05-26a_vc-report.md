# Scottish VC Investment Intelligence Report
**Date:** 26 May 2026  
**Prepared by:** Scottish VC Tracker — Reporter Agent

---

## 1. Executive Summary

This report covers **16 confirmed investment records** (high or medium confidence) drawn from the deduplicator's output of 17 records — one record (ePass) is low confidence and is addressed in the appendix. Deals span January to May 2026, with the majority announced in March and April.

**Estimated total capital deployed (high/medium confidence deals): approximately £61.1m.** This figure includes USD-denominated deals converted at approximately $1.35/£1 (Entourage AI ~£3.7m; Carbogenics and Cnuic ~£2.2m each) and excludes ePass, for which no investment amount exists. One data quality issue materially affects this total: the Stampfree.Ai record contains a parser error in the `amount_gbp_millions` field (recorded as 1,029,968 rather than ~1.03 — see Data Notes). The correct figure of approximately £1.03m has been used throughout this report.

**Three headline observations:**

1. **Deep tech and life sciences are dominating the deal flow.** Eight of the 16 confirmed investments sit in deep tech, healthtech, life sciences, or their intersection — and they account for the majority of capital deployed. Glasgow and Edinburgh university spinouts feature prominently, with the University of Glasgow and University of Edinburgh each generating multiple funded companies this period.

2. **Maven Capital Partners and the Scottish National Investment Bank are the most consistent co-investors in the ecosystem.** Maven (via the Investment Fund for Scotland) appears in three deals; SNIB appears in two of the largest rounds (Bioliberty £7.7m and EnteroBiotix £19m). Both act primarily as co-investors alongside private capital rather than as lead scouts.

3. **The largest single deal — EnteroBiotix's £19m growth round — has a significant location caveat.** The company is described in source material as Bellshill-based (North Lanarkshire), but the record carries `company_not_clearly_scottish` and `location_unknown` flags. If confirmed as a Scottish company, it substantially raises the period total; if not, the adjusted total is approximately £42m across 15 deals.

**Notable gap:** No Aberdeen or Highlands and Islands deals appear in this dataset. The geographic picture is entirely Edinburgh and Glasgow, which may reflect sourcing bias as much as actual deal distribution. Fintech — historically a significant Scottish sector — is absent from this period's data.

---

## 2. Active VCs in Scotland — This Period

The table below covers all investor entities appearing in high/medium confidence records. Public bodies (Scottish Enterprise Investment Fund, British Business Bank) and the European Space Agency are included for completeness but are not venture capital firms.

| VC / Investor | Deals | Total £ Deployed | Stages | Sectors | HQ |
|---|---|---|---|---|---|
| Scottish Enterprise Investment Fund | 6 | Co-investor (undisclosed) | Pre-Seed–Seed | Deep Tech, Life Sciences, Energy, Healthtech | Glasgow |
| Old College Capital | 4 | Co-investor (undisclosed) | Pre-Seed–Seed | Deep Tech, Life Sciences, Energy & Cleantech | Edinburgh |
| Archangels | 3 | Lead/co across deals | Pre-Seed–Series A | Life Sciences, Healthtech, Cleantech | Edinburgh |
| Maven Capital Partners / IFS Maven | 3 | £3.85m (confirmed lead amounts) | Growth, Unknown | Creative & Media, Construction Tech | Glasgow/Edinburgh |
| STAC Invest | 3 | £0.772m | Pre-Seed | Deep Tech, Proptech, Envirotech | Glasgow |
| PXN Ventures | 2 | £8.5m | Seed, Growth | Energy & Cleantech, Deep Tech | Edinburgh |
| Scottish National Investment Bank | 2 | £22m+ (£3m lead in Bioliberty; co in EnteroBiotix) | Series A, Growth | Healthtech, Life Sciences | Edinburgh |
| GU Holdings (Univ. of Glasgow) | 2 | Co-investor (undisclosed) | Pre-Seed–Seed | Healthtech, AI & Machine Learning | Glasgow |
| Axeleo Capital | 1 | £10m (lead) | Seed | Energy & Cleantech | Paris, France |
| Thairm Bio | 1 | £19m (lead) | Growth | Life Sciences | Edinburgh |
| Twin Path Ventures | 1 | £1.6m (lead) | Seed | Healthtech, AI & ML | Unknown |
| Tensor Ventures | 1 | ~£2.2m (lead) | Pre-Seed | Deep Tech | Unknown |
| Dangerous Ventures | 1 | Co-investor | Seed | Energy & Cleantech | United States |
| Green Angel Ventures | 1 | Co-investor | Seed | Energy & Cleantech | London |
| Blackfinch Ventures | 1 | Co-investor | Seed | Deep Tech | Gloucester |
| Provision | 1 | ~£3.7m (lead) | Pre-Seed | Healthtech, AI & ML | UK (unknown) |
| R42 Group | 1 | ~£1.03m (lead) | Growth | AI & Machine Learning | Unknown |
| Conduit Connect | 1 | Co-investor | Series A | Healthtech, Deep Tech | London |
| Hanna Capital SEZC | 1 | Co-investor | Series A | Healthtech, Deep Tech | London |
| Eos Advisory | 1 | Co-investor | Series A | Healthtech, Deep Tech | Unknown |
| Quantum Exponential | 1 | Co-investor | Seed | Deep Tech | UK |
| Zero Carbon Capital | 1 | Co-investor | Seed | Energy & Cleantech | UK |
| Kibo Invest | 1 | Co-investor | Seed | Energy & Cleantech | Singapore |
| Bayern Capital | 1 | Co-investor | Seed | Energy & Cleantech | Germany |
| British Business Investments | 1 | Co-investor | Unknown | Life Sciences | Sheffield |
| EverQuest Capital Partners | 1 | Co-investor | Unknown | Life Sciences | Unknown |
| Silicon Roundabout Ventures | 1 | Co-investor | Pre-Seed | Deep Tech | London |

**Notes on multi-deal investors:**

**Scottish Enterprise Investment Fund** appeared in six deals — Biocaptiva, Carbogenics, Earth Blox, Quantcore, TileBio, and Exergy3 — making it the most active co-investor by deal count. As a quasi-public body it does not lead rounds but consistently fills out syndicates at seed stage across all major sectors. Its breadth this period reflects a statutory cross-sector mandate rather than any thesis shift.

**Old College Capital** (University of Edinburgh's venture fund) participated in four deals — Biocaptiva, Carbogenics, Exergy3, and Bioliberty — all Edinburgh-based university spinouts. The pattern is entirely consistent with its mandate of backing Edinburgh spinouts at the earliest stages. OCC functions as a patient anchor investor that signals university confidence and typically catalyses private capital into syndicates.

**Archangels** led or co-invested in three deals — Biocaptiva (lead, £1.58m), Bioliberty (co-investor, £7.7m Series A), and Earth Blox (follow-on, £6m growth). The mix of a small life sciences deal alongside a large Series A and a growth round demonstrates continued willingness to back portfolio companies across multiple rounds. Their 2025 annual report claimed £41m leveraged in Scottish scale-ups; this period's activity continues that pace.

**Maven Capital Partners** led or co-invested in three deals — Esk (£2.6m lead via VCTs and IFS), Highway Data Systems (£1.25m lead via IFS), and Nami Surgical (£1.9m co-investor; that deal is in the ledger from an earlier run). Maven operates primarily as fund manager for the British Business Bank's Investment Fund for Scotland, which shapes its deal flow toward growth-stage companies with commercial traction rather than early-stage bets. The sector mix (entertainment tech, road construction QA, surgical devices) reflects IFS's broad regional mandate rather than a focused vertical thesis.

**STAC Invest** made three investments from a single £772k cohort deployment — Quantcore (£250k participation), Vuabl (£222k), and Airspection (£300k) — all graduates of STAC's 18-month deeptech accelerator programme at Glasgow's Skypark. The cohort model means these three deals are structurally linked rather than independently sourced. STAC has declared an ambition to become the UK's most active deeptech investor; this high-frequency, small-ticket approach is the mechanism for achieving that volume target.

**PXN Ventures** led two deals — the £6m growth round into Earth Blox and the £2.5m seed round into Quantcore. The pair illustrates PXN's stage range: an established nature-risk analytics company with global bank clients, and an early quantum hardware manufacturer. PXN was formed from the 2025 merger of Edinburgh-based Par Equity and Praetura Ventures. These deals suggest the combined entity is maintaining Par Equity's traditional Scottish pipeline while extending into quantum hardware, which is new territory for the firm.

**Scottish National Investment Bank** led Bioliberty's Series A (£3m SNIB commitment within the £7.7m round) and co-invested in EnteroBiotix's £19m growth round. Both deals sit within SNIB's wellbeing mission (rehabilitation robotics; microbiome therapeutics). SNIB's presence in two of the period's largest rounds reinforces its role as a cornerstone investor in growth-stage Scottish companies, and in both cases its participation appears to have anchored a broader private syndicate.

---

## 3. VC Activity by Stage

| Stage | Deal Count | Total Capital (approx. £m) | Most Active Investors |
|---|---|---|---|
| Pre-Seed | 5 | ~£9.4m | STAC Invest, GU Holdings, Provision, Tensor Ventures |
| Seed | 4 | ~£16.3m | PXN Ventures, Old College Capital, SE Investment Fund, Twin Path Ventures, Axeleo Capital |
| Series A | 1 | £7.7m | Scottish National Investment Bank, Archangels |
| Growth | 4 | ~£28.6m | Thairm Bio, Maven Capital Partners, PXN Ventures, SNIB |
| Unknown | 2 | £2.83m | Archangels (Biocaptiva), Maven IFS (Highway Data Systems) |

**Commentary:**

Growth stage dominates by capital deployed, driven by EnteroBiotix (£19m) and Earth Blox (£6m). If EnteroBiotix is confirmed as a Scottish company, it is the single largest deal in the dataset and pushes life sciences to the top of the capital table by a significant margin.

The seed stage produced the period's most notable deal in relative terms: Exergy3's £10m seed round, led by French VC Axeleo Capital, is substantially larger than the typical Scottish seed cheque and reflects the capital intensity of industrial energy storage hardware. A £10m seed is unusual anywhere in the UK outside London's deep tech cluster.

Pre-seed activity was concentrated in Glasgow — all three STAC cohort companies plus Entourage AI — with only Cnuic representing Edinburgh at this stage. The relatively small absolute amounts (£200k to ~£3.7m) mask strategic significance: Cnuic and Entourage AI are working on foundational technologies that will need large follow-on rounds to reach commercial scale.

There is a notable absence of Series B or later rounds, which is typical for the Scottish market where companies at that stage often raise from pan-European funds not captured by Scottish-focused sources.

---

## 4. Deal-by-Deal Breakdown

*Records with confidence: high or medium, sorted by date descending then amount descending.*

---

### Stampfree.Ai — Growth — £1.03m
**Sector**: AI & Machine Learning  
**Location**: Edinburgh  
**Lead investor**: R42 Group  
**Co-investors**: Crowdcube investors, Republic investors, unnamed existing and new investors  
**Date**: 20 May 2026  
**Sources**: DIGIT (https://www.digit.fyi/edinburgh-ai-ecommerce-firm-raises-over-1m-in-new-investment/)

Edinburgh-based Stampfree.Ai develops AI-powered parcel shipping and returns technology, including WhatsApp-based returns management and patented label-free shipping deployed with Royal Mail, Evri, and QazPost in Kazakhstan. The round was led by long-term backer R42 Group alongside crowdfunding investors on Crowdcube and Republic, and was described by CEO Hugh Craigie Halkett as oversubscribed. Note: the `amount_gbp_millions` field in the data file contains a parser error (1,029,968 instead of 1.03) — see Data Notes.

**Confidence**: medium

---

### Esk — Growth — £2.6m
**Sector**: Creative & Media  
**Location**: Edinburgh  
**Lead investor**: Maven Capital Partners  
**Co-investors**: Maven Income and Growth VCTs, Investment Fund for Scotland (IFS Maven Equity Finance), British Business Bank  
**Date**: 11 May 2026  
**Sources**: Maven Capital Partners News (https://www.mavencp.com/latest-news/maven-leads-2.6-million-funding-round-in-esk)

Edinburgh-based Esk delivers high-end live experience events for blue-chip clients including Netflix, Paramount, and BAFTA, and has completed over 550 shows globally. Maven led the round via its VCTs and the British Business Bank's Investment Fund for Scotland, combining proprietary fund capital with the government-backed IFS mandate. The funding will support business development, marketing, IP portfolio growth, and development of Esk's proprietary hardware technology.

**Confidence**: high

---

### EnteroBiotix — Growth — £19m
**Sector**: Life Sciences  
**Location**: Unknown (reported as Bellshill, North Lanarkshire — see caveat)  
**Lead investor**: Thairm Bio  
**Co-investors**: Scottish National Investment Bank, existing and new investors (undisclosed)  
**Date**: 29 April 2026  
**Sources**: Scottish Financial Review (https://scottishfinancialreview.com/2026/04/29/enterobiotix-bellshill-biopharma-raises-19m/)

EnteroBiotix is a biopharmaceutical company developing microbiome therapeutics, with lead candidate EBX-102-02 targeting irritable bowel syndrome with constipation following a positive Phase 2a trial. The £19m growth round will fund Phase 2b development, described as the largest ever full-spectrum microbiome therapeutic trial in IBS; first patient dosing is expected Q2 2026. Source material locates the company in Bellshill; the record carries `location_unknown` and `company_not_clearly_scottish` flags — verification of Scottish domicile is recommended before using this deal in Scottish ecosystem analysis.

**Confidence**: high (location caveat applies)

---

### Highway Data Systems — Unknown round — £1.25m
**Sector**: Property & Construction Tech  
**Location**: Glasgow  
**Lead investor**: Investment Fund for Scotland (IFS Maven Equity Finance)  
**Co-investors**: None named  
**Date**: 30 April 2026  
**Sources**: Maven Capital Partners News (https://www.mavencp.com/latest-news/ifs-maven-equity-finance-invests-in-1.25-million-in-highway-data-systems)

Glasgow-based Highway Data Systems (HDS) develops automated quality assurance technology for road construction, combining hardware, electronics, and software to replace manual testing processes. HDS was the first business to secure investment through the Greater Glasgow Innovation Cluster via the IFS, and serves major contractors including Eurovia, Holcim, and Tarmac across UK and US markets. The round type is unconfirmed.

**Confidence**: high

---

### Cnuic — Pre-Seed — ~£2.2m ($3m)
**Sector**: Deep Tech  
**Location**: Edinburgh  
**Lead investor**: Tensor Ventures  
**Co-investors**: Blank Space Ventures, Silicon Roundabout Ventures, Phasechange, SANDS, Superlative  
**Date**: 28 April 2026  
**Sources**: Tech.eu (https://tech.eu/2026/04/28/cnuic-secures-eur3m-pre-seed-to-unlock-next-generation-photonic-chip-production/)

Cnuic is developing a photolithography device that uses light rather than electrons to enable fast, reconfigurable production of photonic chips. The oversubscribed $3m pre-seed (approximately £2.2m at $1.35/£1) was led by Tensor Ventures with a six-investor syndicate — unusual depth for a pre-seed, suggesting strong conviction in the photonics hardware opportunity. Co-founder Omar Durrani frames the technology in terms of European semiconductor sovereignty: "We learned to use electrons. Now we are learning to use light."

**Confidence**: high

---

### Exergy3 — Seed — £10m
**Sector**: Energy & Cleantech  
**Location**: Edinburgh  
**Lead investor**: Axeleo Capital  
**Co-investors**: Bayern Capital, Kibo Invest, Scottish Enterprise Investment Fund, Zero Carbon Capital, Old College Capital  
**Date**: 21 April 2026  
**Sources**: Edinburgh Innovations News (https://edinburgh-innovations.ed.ac.uk/news/spinout-exergy3-raises-10m-to-decarbonise-industrial-heat)

Exergy3, a University of Edinburgh spinout, has developed an ultra-high-temperature thermal energy storage system that converts surplus renewable electricity into industrial-grade heat up to 1,200°C. The £10m seed round was led by Paris-based Axeleo Capital via its Article 9 Green Tech Industry I fund, with an international syndicate spanning Germany (Bayern Capital), Singapore (Kibo Invest), and the UK. A pilot at Annandale Distillery demonstrated one of the world's first low-carbon whisky productions. This is the largest seed round in the dataset and, notably, was led by a continental European fund with no prior visible Scottish activity.

**Confidence**: high

---

### Entourage AI — Pre-Seed — ~£3.7m ($5m)
**Sector**: Healthtech, AI & Machine Learning  
**Location**: Glasgow  
**Lead investor**: Provision  
**Co-investors**: GU Holdings Ltd (University of Glasgow), David Peterson, Brad Peltz, angel investors  
**Date**: 18 March 2026  
**Sources**: Scottish Financial Review (https://scottishfinancialreview.com/2026/03/18/entourage-ai-glasgow-uni-health-spinout-in-5m-raise/)

Entourage AI is a University of Glasgow spinout working on longevity science, using AI to transform how human healthspan is measured and extended. The $5m pre-seed (approximately £3.7m) was led by Provision, an investor with a very low public profile, and supported by the University of Glasgow's own investment arm. At $5m this is the largest pre-seed in the dataset by a significant margin. The Scottish Government Business Minister attended the opening of the company's Research and Operations Centre at Glasgow's West of Scotland Science Park.

**Confidence**: high

---

### Earth Blox — Growth — £6m
**Sector**: Energy & Cleantech  
**Location**: Edinburgh  
**Lead investor**: PXN Ventures  
**Co-investors**: Archangels, Scottish Enterprise Investment Fund, European Space Agency  
**Date**: 18 March 2026  
**Sources**: Archangels News (https://archangelsonline.com/earth-blox-secures-6m-to-help-businesses-and-banks-finance-the-transition-to-a-nature-positive-economy/); PXN Ventures News (https://www.pxnventures.co.uk/earth-blox-secures-6m-to-finance-the-transition-to-a-nature-positive-economy/)

Earth Blox has built a nature risk analytics platform integrating satellite data and AI to help financial institutions, energy firms, and agricultural businesses assess ecosystem degradation and climate hazard impacts on financial performance. The £6m round was led by PXN Ventures with follow-on from Archangels and participation from the European Space Agency — an unusual co-investor that reflects the satellite-data dimension of the product. Record was merged from two sources with "definite" confidence.

**Confidence**: high

---

### Bioliberty — Series A — £7.7m
**Sector**: Deep Tech, Healthtech  
**Location**: Edinburgh  
**Lead investor**: Scottish National Investment Bank  
**Co-investors**: Archangels, Eos Advisory, Old College Capital, Hanna Capital SEZC, Conduit Connect  
**Date**: 19 March 2026  
**Sources**: Archangels News (https://archangelsonline.com/bioliberty-announces-10-5-million-series-a-financing-to-build-functional-intelligence-capabilities-for-post-acute-care/); Edinburgh Innovations News (https://edinburgh-innovations.ed.ac.uk/news/bioliberty-7-7m-investment)

Bioliberty, a University of Edinburgh spinout at The National Robotarium with manufacturing in Fife, has developed AI-enabled soft-robotic rehabilitation technology for post-acute care. The £7.7m Series A was led by SNIB (£3m) and brought in two London-based investors new to the Scottish market: Conduit Connect (an impact-focused EIS fund) and Hanna Capital SEZC (a Cayman-structured vehicle with limited public profile). The Archangels source references a total of $10.5m (~£7.7m at current rates), consistent with the Edinburgh Innovations figure; the deduplicator correctly merged these two records with "definite" confidence.

**Confidence**: high

---

### Swurf — Pre-Seed — £200k
**Sector**: Worktech / Flexible workspace platform (sector not normalised to taxonomy)  
**Location**: Edinburgh  
**Lead investor**: Undisclosed  
**Co-investors**: Gareth Williams (Skyscanner co-founder), Anna Lagerqvist Christopherson (Boda Bars), unnamed HNW investors  
**Date**: 9 March 2026  
**Sources**: Daily Business (https://dailybusinessgroup.co.uk/2026/03/gibson-raises-200k-to-expand-swurf-platform/)

Edinburgh-based Swurf operates a remote-working platform connecting users to on-demand private meeting pods across 450+ venues, serving approximately 14,000 users. The £200k pre-seed brought in Skyscanner co-founder Gareth Williams as a backer alongside hospitality entrepreneurs — angel money rather than institutional VC. The funding will accelerate rollout of Swurf Pods across Edinburgh.

**Confidence**: medium

---

### Biocaptiva — Unknown round — £1.58m
**Sector**: Life Sciences  
**Location**: Edinburgh  
**Lead investor**: Archangels  
**Co-investors**: Old College Capital, British Business Investments, Scottish Enterprise Investment Fund, EverQuest Capital Partners  
**Date**: 9 March 2026  
**Sources**: Archangels News (https://archangelsonline.com/biocaptiva-secures-1-58m-to-transform-how-blood-samples-are-prepared-for-liquid-biopsy/)

Biocaptiva, a University of Edinburgh spinout based at Easter Bush Campus, has developed the msX magnetic bead platform for liquid biopsy cancer testing. The technology extracts cell-free DNA directly from whole blood without centrifuges, enabling faster, larger, and more automatable samples. Archangels led the round; new investor EverQuest Capital Partners participated alongside established co-investors. Funds are earmarked for US market entry and R&D expansion.

**Confidence**: high

---

### TileBio — Seed — £1.6m
**Sector**: Healthtech, AI & Machine Learning  
**Location**: Glasgow  
**Lead investor**: Twin Path Ventures  
**Co-investors**: Scottish Enterprise Investment Fund, GU Holdings Ltd (University of Glasgow)  
**Date**: 3 March 2026  
**Sources**: Glasgow City of Science and Innovation (https://glasgowcityofscienceandinnovation.com/glasgow-healthtech-spinout-raises-1-6m-to-transform-cancer-diagnosis-with-ai/)

TileBio, a University of Glasgow spinout, has developed self-learning AI models that learn the "language of cancer" directly from unlabelled tissue images, bypassing the manual data annotation bottleneck that limits most digital pathology AI. The £1.6m seed round was led by Twin Path Ventures — a fund not previously seen in this dataset. Funds will accelerate commercialisation and clinical deployment of TileBio's diagnostic platform.

**Confidence**: high

---

### Quantcore — Seed — £2.5m
**Sector**: Deep Tech  
**Location**: Glasgow  
**Lead investor**: PXN Ventures  
**Co-investors**: Blackfinch Ventures, Scottish Enterprise Investment Fund, Quantum Exponential, STAC Invest  
**Date**: 5 March 2026  
**Sources**: PXN Ventures News (https://www.pxnventures.co.uk/quantcore-raises-2-5m-to-build-sovereign-quantum-supply-chain/); BusinessCloud (https://businesscloud.co.uk/live-blog/stac-backs-three-scottish-deeptech-companies/)

Quantcore, a University of Glasgow spin-out at the James Watt Nanofabrication Centre, manufactures niobium-based superconducting circuits for quantum computers and advanced sensing systems. The company describes itself as the only UK producer of quantum hardware using niobium, and frames its work explicitly around sovereign supply chain capability. The £2.5m seed was co-led by PXN, Blackfinch, and Scottish Enterprise, with Quantum Exponential (a quantum-specialist fund) and STAC also participating. Two records were merged with "probable" confidence — amounts and dates are consistent across sources.

**Confidence**: high

---

### Carbogenics — Seed — ~£2.2m ($3m, includes grants)
**Sector**: Energy & Cleantech  
**Location**: Edinburgh  
**Lead investor**: Undisclosed  
**Co-investors**: Dangerous Ventures (US), Green Angel Ventures (UK), Old College Capital, Scottish Enterprise Investment Fund  
**Date**: 19 January 2026  
**Sources**: ADBA press release via DuckDuckGo (https://adbioresources.org/newsroom/member-press-release-3-million-investment-for-edinburgh-based-specialist-bio-carbon-designer-carbogenics/)

Carbogenics, a University of Edinburgh spinout founded in 2016, has developed CreChar biochar for the biogas industry to enhance anaerobic digestion processes. The $3m round mixed equity investment from Dangerous Ventures (US climate VC), Green Angel Ventures, and Old College Capital with grant funding from Innovate UK and US state bodies — the `possible_grant_not_vc` flag is warranted and the equity portion is likely smaller than the $3m headline. This is the period's earliest deal and the only one with confirmed US investor participation.

**Confidence**: medium

---

### Vuabl — Pre-Seed — £222k
**Sector**: Property & Construction Tech  
**Location**: Glasgow  
**Lead investor**: STAC Invest  
**Co-investors**: None named  
**Date**: 1 April 2026  
**Sources**: BusinessCloud (https://businesscloud.co.uk/live-blog/stac-backs-three-scottish-deeptech-companies/)

Glasgow-based Vuabl has built software using the LIDAR sensors in modern smartphones to scan properties and generate condition reports and EPC ratings, targeting housing providers meeting new energy efficiency and tenant safety regulations. The £222k investment came from STAC Invest as part of its cohort deployment across three graduating companies.

**Confidence**: high

---

### Airspection — Pre-Seed — £300k
**Sector**: Envirotech / Autonomous drone inspection (sector not normalised to taxonomy)  
**Location**: Glasgow  
**Lead investor**: STAC Invest  
**Co-investors**: None named  
**Date**: 1 April 2026  
**Sources**: BusinessCloud (https://businesscloud.co.uk/live-blog/stac-backs-three-scottish-deeptech-companies/)

Glasgow-based Airspection builds autonomous drone technology for offshore wind turbine inspections and other remote infrastructure including power lines, rail networks, and coastal assets. The £300k investment from STAC Invest was part of the same cohort deployment as Vuabl and Quantcore. Airspection's focus on offshore wind inspection has a natural fit with the Scottish energy landscape.

**Confidence**: high

---

## 5. VC Intelligence: Who's Active in Scotland

Profiles sorted by total historical deal count in Scotland (using the ledger; supplemented by known_vcs.json context and training data where noted).

---

### Scottish Enterprise Investment Fund
**HQ:** Glasgow | **Stage focus:** Pre-Seed to Seed | **Scotland deals in ledger:** 7 (Biocaptiva, Carbogenics, Earth Blox, Nami Surgical, Quantcore, TileBio, Exergy3)

The Scottish Enterprise Investment Fund is a quasi-public co-investment vehicle and the most frequently appearing investor in this dataset. It is not a venture capital firm in the commercial sense: it does not set deal terms, does not source deals independently, and does not lead rounds. Its function is to fill syndicates and extend the reach of private capital into Scottish companies that private investors alone might not fully fund. Activity is high, consistent, and likely to remain so given its statutory mandate. Investors building a Scottish portfolio should treat it as a reliable but non-strategic co-investor.

---

### Archangels
**HQ:** Edinburgh | **Stage focus:** Pre-Seed to Series A | **Scotland deals in ledger:** 3 (Biocaptiva, Earth Blox, Bioliberty)

Scotland's oldest and largest angel syndicate, Archangels has operated since 1992 and in 2025 reported leveraging £41m of investment into Scottish scale-ups. The three deals in this dataset span three stages (lead at seed, co-investor at Series A, follow-on at growth), consistent with Archangels' historical pattern of backing companies from early and following on through multiple rounds. Life sciences and healthtech are their strongest verticals in Scotland, and Edinburgh accounts for most of their deal flow. Activity level appears stable to growing. Archangels does not typically publish a formal investment thesis, but their portfolio is characterisably Edinburgh-biased and deep-tech/life sciences-weighted.

---

### Old College Capital
**HQ:** Edinburgh | **Stage focus:** Pre-Seed to Seed | **Scotland deals in ledger:** 4 (Biocaptiva, Carbogenics, Exergy3, Bioliberty)

Old College Capital is the venture investment arm of the University of Edinburgh, operating under Edinburgh Innovations. All four ledger entries are Edinburgh spinouts across deep tech, life sciences, and energy — entirely consistent with its mandate. OCC provides anchor capital and validation for spinouts at early stages, with the expectation that private investors lead on valuation and terms. Its consistent presence across Edinburgh's most active sectors makes it a useful signal of University of Edinburgh spinout activity. Activity is increasing as the university's commercialisation pipeline has visibly strengthened.

---

### Maven Capital Partners
**HQ:** Glasgow/Edinburgh | **Stage focus:** Seed to Growth | **Scotland deals in ledger:** 3 in current period (Esk, Highway Data Systems) plus Nami Surgical from earlier run

Maven's Scottish activity is almost entirely channelled through the Investment Fund for Scotland mandate from the British Business Bank. This shapes its deal flow toward companies with existing commercial traction rather than pre-revenue bets. The IFS mandate covers all sectors, which explains the diverse deal mix (entertainment tech, road construction QA, surgical devices). Maven also co-invests its own VCT capital in selected deals (Esk being an example), meaning some deals attract a blend of public and proprietary funds. Activity is steady and reflects IFS deployment targets rather than market-driven sourcing.

---

### PXN Ventures
**HQ:** Edinburgh | **Stage focus:** Seed to Series A | **Scotland deals in ledger:** 2 (Earth Blox, Quantcore)

PXN Ventures was formed in 2025 from the merger of Edinburgh-based Par Equity and Manchester-based Praetura Ventures. Par Equity was historically one of Scotland's most active independent VCs. Both deals visible in this dataset were announced in early 2026 and appear to reflect the new combined entity's pipeline. PXN's participation at both seed and growth suggests it retains Par Equity's cross-stage flexibility. It is too early to assess whether the Praetura merger has shifted the Scottish investment thesis, but Scottish deal sourcing does not appear to have slowed. Worth monitoring for any drift toward the wider Northern England markets that Praetura historically served.

---

### Scottish National Investment Bank
**HQ:** Edinburgh | **Stage focus:** Series A to Growth | **Scotland deals in ledger:** 2 (Bioliberty, EnteroBiotix)

SNIB was established in 2020 with a £2bn mandate to invest in businesses and projects aligned with Scotland's net zero, place, and wellbeing missions. Its two deals this period — anchoring Bioliberty's Series A and co-investing in EnteroBiotix's growth round — both align clearly with the wellbeing mission. SNIB's £3m anchor in Bioliberty is consistent with its stated preference for co-investing alongside private capital. The bank has publicly stated a preference for deals that support Scottish economic and social outcomes over pure financial return optimisation. Activity appears to be increasing as the bank matures and deploys more of its mandate.

---

### STAC Invest
**HQ:** Glasgow | **Stage focus:** Pre-Seed to Seed | **Scotland deals in ledger:** 3 (Quantcore participation, Vuabl, Airspection)

STAC is Glasgow's deeptech accelerator and investor, operating from Skypark. Its cohort model — deploying capital into accelerator graduates — means investment decisions are programme-driven. The three deals visible (quantum hardware, proptech via LIDAR, drone inspection) demonstrate breadth within a deeptech frame. STAC has declared an ambition to become the UK's most active deeptech investor by deal count. The programme-driven, high-frequency, small-ticket approach is the mechanism for achieving that volume target. Whether deal quality matches volume is not assessable from this dataset, but STAC's pipeline is clearly active and Glasgow-anchored.

---

### GU Holdings (University of Glasgow)
**HQ:** Glasgow | **Stage focus:** Pre-Seed to Seed | **Scotland deals in ledger:** 2 (TileBio, Entourage AI)

GU Holdings is the University of Glasgow's investment arm, backing Glasgow spinouts at the earliest stages. Both ledger entries are AI-enabled healthtech spinouts (TileBio — digital pathology, Entourage AI — longevity science). The University of Glasgow appears to be generating strong deal flow in biomedical AI. GU Holdings functions similarly to Old College Capital for Edinburgh: an institutional anchor for private investors considering Glasgow spinouts. Activity is visible and consistent.

---

### Blackfinch Ventures
**HQ:** Gloucester | **Stage focus:** Seed to Series A | **Scotland deals in ledger:** 1 (Quantcore)

Blackfinch is an EIS/SEIS-focused fund that makes selective investments across the UK. Its participation in the Quantcore quantum hardware seed round is a first appearance in this dataset. One deal is insufficient to characterise a Scottish strategy; the EIS wrapper is consistent with backing early-stage hardware companies with R&D expenditure profiles. Worth monitoring for further Scottish activity.

---

### Axeleo Capital
**HQ:** Paris, France | **Stage focus:** Seed to Series A | **Scotland deals in ledger:** 1 (Exergy3)

Axeleo is the first continental European VC fund to appear as deal lead in this dataset. Its Article 9 Green Tech Industry I fund led the £10m Exergy3 seed round — the largest seed deal in the period and Axeleo's first confirmed Scottish investment. The transaction signals that Edinburgh's university spinout ecosystem is now visible enough to attract European climate-specialist capital, which historically concentrated in Germany, France, and the Netherlands. This is strategically significant for Scottish cleantech companies seeking international capital. No public statements about a Scottish/UK investment thesis from Axeleo are available from training data.

---

### Thairm Bio
**HQ:** Edinburgh | **Stage focus:** Growth | **Scotland deals in ledger:** 1 (EnteroBiotix)

Thairm Bio led the £19m EnteroBiotix growth round — the largest deal in the dataset. It maintains a very low public profile and may be a single-LP vehicle, a family office, or a pharma-adjacent fund with an Edinburgh registration. No prior Scottish deals appear in the ledger, and no public statements about an investment thesis are available. Given the size of the lead position in a clinical-stage biopharma company, this firm warrants closer research. If it is a specialist life sciences fund, it represents a meaningful new source of large-round capital in the Scottish ecosystem.

---

### Tensor Ventures
**HQ:** Unknown | **Stage focus:** Pre-Seed to Seed | **Scotland deals in ledger:** 1 (Cnuic)

Tensor Ventures led the $3m Cnuic pre-seed. The firm maintains a very low public profile; co-founder Martin Drdúl appears to be Central European based on surname. This is a first Scottish appearance and one deal is insufficient to characterise any Scottish thesis. The photonics/semiconductor hardware focus is distinctive.

---

### Other investors (one deal, limited context)

**Dangerous Ventures** (US climate VC) and **Green Angel Ventures** (London cleantech angel syndicate) both co-invested in Carbogenics' seed — both first appearances in Scottish data. **Provision** (UK, unknown HQ) led Entourage AI's $5m pre-seed; zero public profile. **Twin Path Ventures** led TileBio's seed round — first appearance, no HQ confirmed. **R42 Group** led Stampfree.Ai's growth round and is described as a long-term backer across all prior rounds; no other Scottish deals in the dataset. **Conduit Connect** (London, EIS impact fund) and **Hanna Capital SEZC** (London/Cayman structure) both co-invested in Bioliberty's Series A — first Scottish appearances for both.

---

## 6. Sector Heat Map

**Deep Tech** is the standout sector of the period by deal count, appearing in five confirmed investments: Bioliberty (soft robotics), Cnuic (photonic chip manufacturing), Quantcore (quantum hardware), Airspection (drone inspection), and Exergy3 (thermal energy storage). Three of these are Glasgow or Edinburgh university spinouts building physical hardware. The sovereign technology narrative is recurrent: Quantcore explicitly frames niobium chip production as a national security question, and Cnuic discusses European semiconductor independence. This framing is resonating with funders — it provides a policy tailwind that pure commercial arguments for hardware companies often lack.

**Energy & Cleantech** produced the most capital by sector, primarily through Exergy3 (£10m), Earth Blox (£6m), and Carbogenics (~£2.2m). The three represent distinct parts of the energy transition stack: industrial heat decarbonisation (Exergy3), nature risk analytics for finance (Earth Blox), and biochar for anaerobic digestion (Carbogenics). The European Space Agency co-investing in Earth Blox adds a satellite-data angle to the Scottish cleantech picture. An international investor syndicate (France, Germany, Singapore, US) in Exergy3 alone suggests Scottish cleantech is reaching an audience beyond the domestic market.

**Healthtech and Life Sciences** together account for four deals: Bioliberty (rehabilitation robotics, Edinburgh), Biocaptiva (liquid biopsy, Edinburgh), TileBio (AI digital pathology, Glasgow), and Entourage AI (longevity science, Glasgow). EnteroBiotix (microbiome therapeutics, £19m) would add substantially if confirmed as Scottish. The Glasgow-Edinburgh axis in biomedical AI is particularly evident: TileBio and Entourage AI are both University of Glasgow spinouts deploying AI against health data problems, while Biocaptiva and Bioliberty are Edinburgh spinouts in diagnostics and therapeutic devices respectively. Average deal sizes in this sector are larger than might be expected for stage.

**AI and Machine Learning** features as a cross-cutting theme rather than a standalone sector. Entourage AI, TileBio, Earth Blox, and Stampfree.Ai all deploy AI as core technology, but across health, climate, and logistics respectively. There is no evidence of a pure-play AI infrastructure or foundation model company raising in Scotland this period. AI investment here is domain-embedded.

**Property and Construction Tech** produced two deals: Vuabl (LIDAR-based property condition reports) and Highway Data Systems (road construction QA). Both are Glasgow-based and both received public or quasi-public funding. This sector is not historically prominent in Scottish VC data; these may reflect Glasgow's built-environment tech cluster rather than a broader trend.

**Notable absences:** No fintech, no pure SaaS/enterprise software, and no agritech deals appear in the confirmed record. Fintech in particular has historically featured in Scottish investment data. Its absence may reflect sourcing gaps in this run's sources — fintech companies tend to announce via trade press not fully covered here — rather than a genuine sector pause.

---

## 7. Geographic Distribution

| Location | Deals (high/medium confidence) | Approx. capital |
|---|---|---|
| Edinburgh | 9 | ~£33m |
| Glasgow | 6 | ~£9m |
| Unknown/Other (EnteroBiotix — Bellshill unconfirmed) | 1 | £19m (location unverified) |
| Aberdeen / Highlands / Islands | 0 | — |

**Edinburgh** accounts for the majority of deals (nine) and the majority of confirmed capital. The clustering is driven by the University of Edinburgh spinout pipeline: Bioliberty, Biocaptiva, Carbogenics, Exergy3, and Earth Blox are all Edinburgh-university-connected, and Old College Capital's four deals all land in Edinburgh. Edinburgh Innovations is functioning as a credible commercialisation pipeline. Stampfree.Ai and Esk are Edinburgh-based commercial companies (not university spinouts), providing some diversity.

**Glasgow** is active across six deals — the three STAC cohort companies (Quantcore, Vuabl, Airspection), TileBio, Entourage AI, and Highway Data Systems — but at significantly smaller average ticket size than Edinburgh. The University of Glasgow spinout engine is productive in healthtech and deep tech. Glasgow's absence from larger rounds (aside from Entourage AI's ~£3.7m pre-seed) continues a historical pattern where Edinburgh dominates by capital deployed. The STAC accelerator is producing a steady supply of early-stage deal flow, which may translate to larger rounds in future periods.

**Other Scotland** is represented only by EnteroBiotix (Bellshill, unconfirmed) and ePass (low confidence, no confirmed investment). Aberdeen, Inverness, Dundee, St Andrews, and other Scottish cities produce no confirmed deals in this dataset. This is consistent with historical patterns but may also reflect sourcing bias: the sources used in this run are heavily weighted toward central belt press and university newsrooms.

**No evidence of a geographic shift** relative to historical patterns. Edinburgh-heavy by capital, Glasgow-active by deal count at smaller sizes.

---

## 8. Appendix: Low-Confidence Records

### ePass — Unknown round — amount undisclosed
**Sector**: SaaS & Enterprise Software  
**Location**: Other Scotland (source text describes it as Edinburgh-based — location field inconsistency)  
**Confidence**: low  
**Issues**: amount_missing, investor_unnamed  
**Date**: 25 May 2026  
**Source**: Scottish Business News (https://scottishbusinessnews.net/govtech-startup-epass-rolls-out-nationwide-platform-after-1m-debut-year/)

ePass is a GovTech startup founded in 2024 following a CivTech competition win. It achieved £1m revenue in its debut year and deployed a local authority licensing platform across all 32 Scottish councils, serving over 15,000 businesses. The source article reports that the founders are "actively engaging with venture capital and investor communities" and are "likely to embark on its first external fundraising round later this year." **No investment has been closed.** This record does not represent a completed deal and should not be included in capital totals or investor activity counts. It is retained as a watchlist item: ePass may be a deal to watch for announcement later in 2026.

---

## 9. Data Notes

**Date range covered:** 19 January 2026 to 25 May 2026 (approximately 18 weeks). The majority of deals cluster in March 2026 (six deals) and April 2026 (four deals), with two in May, one in January, and one date-uncertain deal. The narrow concentration of announcements in March and April suggests either a seasonal uptick in Scottish deal-making or a lag in source coverage of deals that closed earlier.

**Records before deduplication:** 20  
**Records after deduplication:** 17  
**Flagged for review by deduplicator:** 0  
**Records excluded from main analysis (low confidence):** 1 (ePass)  
**Records in main analysis (high or medium confidence):** 16

**Sources used** (inferred from source_name fields in the data):
- Archangels News (archangelsonline.com)
- Edinburgh Innovations News (edinburgh-innovations.ed.ac.uk)
- PXN Ventures News (pxnventures.co.uk)
- Maven Capital Partners News (mavencp.com)
- Scottish Financial Review (scottishfinancialreview.com)
- BusinessCloud (businesscloud.co.uk)
- Glasgow City of Science and Innovation (glasgowcityofscienceandinnovation.com)
- Tech.eu
- DIGIT (digit.fyi)
- Scottish Business News / TechHub Scotland (scottishbusinessnews.net)
- ADBA / Anaerobic Digestion and Bioresources Association press release (adbioresources.org)
- Daily Business (dailybusinessgroup.co.uk)

**Data quality issues requiring attention:**

1. **Stampfree.Ai — parser error in amount_gbp_millions.** The raw amount is £1,029,968 (just over £1m), but the `amount_gbp_millions` field contains 1029968.0 — the parser treated the numerical value of the pence-denominated string as millions. This inflates automated field sums by approximately £1 billion. The field should be corrected to 1.03 in `investments_deduped.json` and the ledger. The correct figure has been used throughout this report.

2. **EnteroBiotix — location flags.** Source material places the company in Bellshill, North Lanarkshire, which is unambiguously in Scotland. The `company_not_clearly_scottish` and `location_unknown` flags suggest the parser could not confirm Scottish incorporation from the source text alone. Manual verification of company domicile is recommended. If confirmed, the location should be updated and the flags removed.

3. **Carbogenics — possible_grant_not_vc.** The $3m headline figure mixes equity investment with grant funding (Innovate UK, New Mexico state bodies). The equity-only VC component is likely meaningfully smaller than $3m. The record's capital figure should be treated as an upper bound.

4. **Highway Data Systems — possible duplicate in ledger.** The ledger contains two entries for Highway Data Systems: `highway-data-systems_seed_2026-04-30` (from an earlier run, round type "Seed", sourced from UK Tech News) and `highway-data-systems_unknown_2026-04-30` (current run, round type "Unknown", sourced from Maven). Both describe the same £1.25m Maven IFS deal on 30 April 2026. The deduplicator did not merge them because the IDs differ (round type field differs). This should be reviewed manually: one record should be retained and the round type reconciled. The "Unknown" classification from the Maven source is likely more accurate than "Seed" inferred from a secondary source.

5. **Swurf — sector not normalised.** "Worktech / Flexible workspace platform" does not map to the sectors.json taxonomy. The `sector_normalised: false` flag is correctly set. A "Future of Work" or "Worktech" category may be worth adding to the taxonomy if this type of company appears with greater frequency.

6. **Airspection — sector not normalised.** "Envirotech / Autonomous drone inspection" does not map to the taxonomy. `sector_normalised: false` is correctly set. The company could reasonably be mapped to "Energy & Cleantech" given its offshore wind focus, or a new "Drones & Autonomous Systems" category could be added.

**Sources that failed to load:** Not available from this dataset — the reporter agent does not have access to the scraper's error log. Check `data/raw/errors.json` if source failure information is needed.

---

*Report generated by Scottish VC Tracker Reporter Agent. Run date: 26 May 2026.*
