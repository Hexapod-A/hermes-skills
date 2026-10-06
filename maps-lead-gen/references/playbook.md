# Google Maps lead playbook (condensed)

Source: Christian (@coldemailchris), "Scrape Local Businesses From Google Maps (FULL COURSE)", posted Oct 4 2026,
https://x.com/coldemailchris/status/2106847718639632443. Numbers below are the article's own claims, not ours.

## Why Maps
Local owners have a Google listing, a phone and an old website, and answer their own phone. LinkedIn/Apollo miss
most of the local service market; the article puts the Maps market at roughly 10x what those databases show.
A list is ready for outbound only when each row has an owner name, a working email and a reason to contact them.

## Market selection
- 1 niche, 1 area, 1 offer. Several niches at once kills reply rate first.
- High-value-customer niches: dentists, med spas, roofers, law firms (one new customer is worth a lot).
- Size: a few thousand businesses across the area. A few hundred runs out fast.
- For 3xAgentic: pick ONE offer per campaign - missed-call text-back, AI receptionist, or speed-to-lead.

## Pull
- Fields: name, phone, website, address, category, star rating, review count.
- Zip code by zip code (the US has 32,000+ zips; each search returns its own batch; a city search shows a fraction).
- Review-count filter: min drops tiny shops, max drops chains with their own buying process.
- Re-pull every campaign: a 3-month-old list is stale.

## Data sources and costs (per the article, Oct 2026)
| Source | What the article says |
|---|---|
| MapsData | Maps listings with emails taken from each business's site. Free: 500 leads with emails/month. Starter $15/mo (yearly) for 10,000/mo. Pro $39/mo (yearly) for 50,000/mo. Scale $79/mo (yearly) for 300,000/mo, up to 100,000 per search, API access; about $3.30 per 10,000 leads; you pay only for leads with an email. US, Canada, UK, Australia; 4,000+ business types. |
| RapidAPI endpoints | around $250 for 2.5 million raw results |
| Apify | roughly 5-10x more expensive |
| Serpdeck | cheap but more limited |
| D7 | most data points per business, higher price |
Advice: test a new niche on the MapsData free tier; once the offer works, Scale is the cheapest volume with emails.
(MapsData's own pricing page, read 2026-10-06, shows the same yearly prices, monthly billing at $19/$49/$99, and API on Pro and Scale.)
Google Places API and Serper are not priced in the article; check their pricing pages before a big run.
This skill: OSM is free; `pull.py` adapters exist for mapsdata, google_places, serper and rapidapi (key-gated).

## Owner name
- Crawl About, Team, Contact pages and footer bios. The article says a crawl finds the owner ~80% of the time
  (our free test on Austin dentists: 10 of 19 with the strict LLM rule, 15 of 19 with the regex layer).
- Backup in the article: Prospeo people search.
- Prompt rule: only a name shown next to owner/founder/principal/doctor, else "not found". A made-up first name
  destroys trust and hurts sending reputation. Check 50 by hand before the full list.
- Cost: instructions at the top, per-business variables at the bottom (prompt caching).

## Email
- One finder alone: 40-60% valid. Several in a row: ~90%. Article order: Prospeo -> Icypeas -> website crawl.
  (This skill runs the free crawl first to save credits; `--order` changes it.)
- Stop at the first valid email; log the source; after a few campaigns the log shows which tools pay off.
- Verify everything (MillionVerifier), second check for catch-alls (BounceBan). Bounce rate under 1%.
- General inboxes (info@, team@) work for LOCAL SERVICE businesses: in one list, general addresses took 54.97
  contacts per lead vs 94.94 for named ones. Not for ecommerce (general inboxes go unread there).
- Send general-inbox campaigns from separate inboxes so a weaker campaign stays away from the main setup.

## Writing
- Not "saw your Google listing". Use a local market fact: a nearby business they'd recognise, a local competitor
  (when the comparison is true), their reviews only if 4 stars or higher.
- Article data: naming the prospect's project and location -> 14.5% reply rate vs 1-3% without (1,160 campaigns).
- Shape: one local detail, one clear offer, one question. Lead with a free useful offer (review audit, ranking vs
  nearby competitors, a sample).

## Calling
- Every listing has a phone; owners live on the phone. Call highest scores first.
- Open with why you're calling using a fact from their listing; ask if that problem is costing them work this month;
  offer a specific meeting time.
- Log the hour of every connect for 2 weeks; then dial in the hours that answer most.

## Intent score, dedupe, suppression
- Points for slow-quote / slow-response complaints in reviews, relevant job postings, a burst of fresh reviews in the
  last 90 days. Call the top first.
- Dedupe on business name + city + email domain. Remove anyone already contacted.

## Rules
- US courts have backed collecting public business data (the article cites hiQ Labs v. LinkedIn). How the list is
  used is John's responsibility: CAN-SPAM, GDPR, CASL where they apply. Check with a lawyer for his case.
- The mistake: stopping at the CSV. Outbound needs owner name + working email on every row.

## First week (article)
Pick one niche and area -> pull 500 -> crawl sites for owner names -> email waterfall + verify -> one local fact
per lead -> send a small batch and start calling -> keep what gets replies; expand to new areas before new niches.
