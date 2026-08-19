# GeoCoderZ — Viva Question Set (Plain English Edition)
## Place-Name Extraction & Canonical Mapping for Geospatial Queries — SIH 2026, PS-09

> **How to use this document:** This is written so that even someone who has never seen the code or the slides can read a question, read the answer, and fully understand what the project does and why. Every technical term is explained the first time it appears. Read this top to bottom once before the viva, then use it as a quick-reference during rapid-fire.

---

## PART 1 — THE BIG PICTURE (Start Here)

### Q1. In one or two sentences, what does this project actually do?

**Answer:**
It reads a piece of text — like a news report or an emergency alert — finds the names of places mentioned in it (like "Thane" or "Kalyan"), and figures out exactly *where those places are* on a map, giving map coordinates (latitude and longitude) for each one. If a name is confusing or could mean more than one place, it also explains, in plain language, why it picked the location it picked.

Think of it like this: if you handed a friend a newspaper clipping and asked them to circle every city mentioned and mark it on a map — that's the job. Our system does that automatically, in seconds, for hundreds of reports.

---

### Q2. Who is this for? Why would anyone need this?

**Answer:**
This is built for people whose *job* is to read incoming reports and quickly understand "what is happening, and where." Specifically:

- People who monitor the news for a living and track incidents (called **OSINT analysts** — OSINT stands for "Open Source Intelligence," meaning information gathered from publicly available sources like news articles, social media, etc.)
- People who work in government disaster-management control rooms, who receive incoming reports during floods, earthquakes, accidents, etc., and need to know exactly where help is needed

This is **not** an app for the general public. A regular citizen won't open this app to check the weather or find a restaurant. It's a tool sitting quietly in the background of a "situation room," helping the people whose job is to make fast decisions during emergencies.

**Why they need it:** Right now, these people read a report by hand and manually look up every place name on Google Maps or a paper map, one at a time. That's slow, and slow is dangerous during an emergency.

---

### Q3. What problem, specifically, are you solving? Walk me through an example.

**Answer:**
Here's a realistic example. Imagine a report comes in that says:

> *"Flooding reported near Thane, spreading toward Kalyan. Springfield authorities also on alert."*

A human reading this has to:
1. Recognize that "Thane," "Kalyan," and "Springfield" are place names (and not, say, people's names or random words)
2. Look each one up
3. Realize that "Thane" could refer to more than one place in the world — there could be a Thane in India and, hypothetically, other places with similar names elsewhere
4. Figure out *which* Thane is correct — obviously the one near Kalyan, in Maharashtra, India — using context clues
5. Realize "Springfield" is a very famous *fictional* example of an ambiguous place name (there are Springfields in many countries) and this one likely doesn't exist as a real place in India at all — so it should fail to resolve, honestly, rather than guess wrong
6. Manually type in coordinates or click on the correct spot on a map

That whole process takes real time — maybe 30 seconds to a minute per place name, if done carefully. If a report has 5, 10, or 20 place names, and there are dozens of reports coming in during a disaster, this adds up to a serious bottleneck. And if a tired human makes a mistake and picks the wrong "Thane," rescue resources could be sent to entirely the wrong location.

**Our system automates all six of those steps** and does it in under 2 seconds, while also telling the analyst *why* it made the choice it made, and how confident it is.

---

### Q4. What's the single most important feature to remember about this project?

**Answer:**
If you remember only one thing, remember this: **the system never lies about how sure it is.**

Every single result comes with:
- A **confidence score** (a number between 0 and 1, like 0.94 or 0.5) that tells the analyst how trustworthy this specific answer is
- A **plain-English reason** explaining exactly why this place was chosen (for example: "This matched based on nearby places mentioned in the same report" or "Nothing else supported this choice, so this is only a population-based guess — please double check")
- If the system genuinely cannot figure out where a place is, it says so clearly — it marks that entry as **"failed"** instead of quietly making up a wrong answer

This matters because in a real emergency, a wrong but *confident-looking* answer is far more dangerous than an honest "I don't know." A tool that quietly guesses wrong locations could send rescue teams to the wrong village. A tool that says "I'm not sure, please verify" lets a human make the final call. We deliberately built the second kind of tool.

---

## PART 2 — HOW IT WORKS (Step by Step, No Jargon)

### Q5. Can you explain the whole process from start to finish, like you're explaining it to your grandparent?

**Answer:**
Sure — imagine you hand the system a paragraph of text. Here's what happens, step by step:

**Step 1 — Reading and spotting place names ("Extraction")**
The system reads through the sentence and picks out any words that look like they're naming a place — a city, a town, a district. It's a bit like using a highlighter to mark every place name in a printed news article. This is done using a well-known AI language tool (called **spaCy**), which has been trained to recognize things like place names, person names, dates, etc., in ordinary text.

**Step 2 — Cleaning up the spelling ("Cleanup")**
Sometimes place names are written differently by different people — old names, nicknames, or slightly different spellings ("Bombay" instead of "Mumbai," for example). The system checks the spotted name against a list of known alternate names and corrects it to the modern, official name if there's a match. This uses a tool called **rapidfuzz**, which is good at recognizing when two spellings are "close enough" to be the same word, even if they're not written identically.

**Step 3 — Looking it up ("Candidate Lookup")**
Now the system searches a big offline database of Indian place names (called **GeoNames India**) to find every place that matches this cleaned-up name. Sometimes there's only one match. Sometimes — especially for common names — there could be several places in India with the same or similar name, and the system needs to pick the right one.

If nothing is found in the local Indian database, the system tries an online lookup service called **Nominatim**, but it's told to only look *within India* (this is a deliberate choice, explained more in Q11).

**Step 4 — Picking the right one ("Disambiguation")**
This is the smartest part of the system. If there are multiple possible matches, it has to decide which one is actually correct. It uses three clues, a bit like a detective:
- **Is it near other places already found in the same report?** (If "Kalyan" is mentioned right after "Thane," and Thane is a real, resolved location, the system checks: is there a Kalyan close by? If yes, that's a strong clue.)
- **Does the surrounding text mention a state or district name?** (If the report says "...in Raigad district," the system prefers candidates actually located in Raigad.)
- **How big/well-known is the place?** (As a last resort, it slightly favors bigger, more well-known places — but only when there's no other evidence, and even then, it flags this pick as "less certain.")

**Step 5 — Putting it together ("Response Assembly")**
Finally, the system collects results for every place name found in the original text, puts them back in the same order they appeared in the sentence, and sends back a clean, structured answer with coordinates, confidence scores, and explanations for each one — ready to be shown as pins on a map.

---

### Q6. What actually shows up on the screen for the person using this?

**Answer:**
The person using the tool sees:
1. A **text box** where they paste in the report they want to analyze
2. After clicking submit, the **original text**, with every place name automatically highlighted
3. A **map** with a pin dropped at every location that was successfully found
4. If they **click on a highlighted name or a map pin**, a small panel pops up explaining *why* that location was chosen and *how confident* the system is — written in plain, readable language, not computer code
5. If a place name **couldn't** be resolved, it's shown differently (like a greyed-out label or a small "couldn't find this" tag), and no pin is placed for it — so the analyst is never misled into thinking every single name was successfully located

This "click to see the reasoning" feature is considered the single most important part of the demo, because it's the part that proves the system is actually *thinking through* the decision — not just doing a random guess and pretending to be sure.

---

### Q7. What happens if the text has no place names at all, or if a place name can't be resolved?

**Answer:**
We planned carefully for both of these situations because a good system needs to handle "boring" cases gracefully, not just the exciting ones.

**Case A — No place names found:**
If someone pastes in a sentence like "The weather today is sunny with a light breeze," the system correctly recognizes that there are zero place names to find. Instead of wasting time running the full pipeline for nothing, it immediately stops and returns a clear message: "No locations found in the provided text." On the screen, the user sees an obvious "no locations detected" message instead of a confusing blank map.

**Case B — A place name is found but can't be matched to a real location:**
This happens, for example, if the text mentions a name that simply isn't a real place in India — like the earlier "Springfield" example. In this situation, the whole request doesn't fail — only that *specific* place name is marked as "failed," with an honest explanation like "No local match found; India-focused fallback search also returned no results." Every *other* place name in the same sentence still resolves normally. One bad name never breaks the whole analysis.

This matters a lot in real usage — reports often mention 5-10 places, and it would be a poor design if one confusing name caused the entire report to fail to process.

---

## PART 3 — WHY WE BUILT IT THIS WAY (Design Decisions Explained Simply)

### Q8. Why does the system only look for places *inside India*? Isn't that limiting?

**Answer:**
Yes, it's a deliberate limitation, and we're upfront about it rather than hiding it.

Here's the reasoning: our local database (GeoNames India) only contains Indian places. If we let the *online fallback search* look anywhere in the world, there's a real risk it would confidently return a matching place name from a completely different country — imagine the system reporting a flood alert in "Thane" but silently pointing to a same-named town somewhere overseas, with no warning that anything was wrong. That's a dangerous, silent failure — the pin looks correct on the map, but it's actually in the wrong country entirely.

By deliberately restricting the online fallback search to India only, we make sure that:
- If a name genuinely isn't a known place in India, the system says so clearly ("failed to resolve") instead of confidently showing the wrong country
- Everyone using the tool — analysts and disaster response teams — is working with a system whose entire "world" is scoped to India, matching how it's actually meant to be used

This means a name like "Springfield" (which doesn't exist as an Indian place) will *always* fail to resolve under our system. We consider that correct behavior, not a bug — it's an honest boundary of the tool, and we say so plainly if anyone tests it.

---

### Q9. Why is "confidence" scored the way it is? Why cap some scores at 0.5 or 0.6?

**Answer:**
Great question, because this is one of the most thoughtful design choices in the whole project.

Imagine the system finds three possible candidates for a place name, and the *only* thing it knows to compare them by is which one is the biggest, most populated place. That's a weak kind of evidence — it's basically saying "well, if I had to guess with zero other information, I'd guess the bigger city." That guess might be right sometimes, but it's a guess, not real evidence from the actual text.

So we made a rule: **if population size is the only reason for a pick, the confidence score can never go above 0.5 (later refined further to a hard ceiling of 0.6).** This way, when an analyst sees a location with, say, 0.45 confidence, they instantly understand: "this was basically a guess based on which place is more famous — I should double check this one manually before relying on it."

Compare that to a location that scored 0.94 confidence because it was an exact database match *and* it was geographically close to another confirmed place mentioned in the same report — that's real, multi-layered evidence, and a much safer bet.

**In simple terms:** we made the system honest about the *quality* of its evidence, not just whether it found *an* answer. A guess dressed up to look confident is worse than useless in a disaster response context — it could get someone killed by sending help to the wrong place with false certainty.

---

### Q10. What is this "caching" thing mentioned in the presentation, and why does it matter?

**Answer:**
"Caching" simply means: **remembering answers you've already worked out, so you don't have to redo the same work again.**

Here's a simple analogy: imagine you're a translator, and someone asks you to translate the word "hello" into French. You look it up once, and the answer is "bonjour." The next time anyone asks you to translate "hello," you don't need to look it up again — you already know the answer. That's caching.

In our system, once a place name like "Thane" has been correctly figured out and located on the map, we save that answer. The next time *any* report — even a completely different report, submitted at a different time — mentions "Thane," the system doesn't have to redo all the detective work (checking databases, doing disambiguation, etc.). It just instantly reuses the answer it already knows.

**Why this matters practically:**
1. **Speed:** Common place names (major cities, well-known districts) get resolved almost instantly after the first time they're seen, because the system already "remembers" them.
2. **Reduced load on external services:** The online fallback search service (Nominatim) has a strict limit — it only allows 1 request per second. If we had to re-look-up "Mumbai" every single time it appeared in a report, we'd quickly hit that limit and slow everything down. By remembering answers, we barely need to use the online service at all after the system has been running for a while.
3. **The system gets smarter and faster the more it's used** — this is a genuinely valuable long-term property, not just a one-time speed trick.

We actually built **two layers** of this remembering system — one that remembers the *exact* spelling someone typed (super fast, catches repeats and misspellings that were seen before), and one that remembers the *cleaned-up, standardized* name (catches new misspellings of a place we've already correctly identified before, even if this exact spelling is new). This two-layer design means the system becomes more useful the longer it runs and the more reports it processes.

---

### Q11. Why did you decide NOT to cache place names that fail to resolve?

**Answer:**
This is a subtle but important decision. At first, it might seem obvious to also "remember" failures, so the system doesn't waste time repeating the same failed search. But we deliberately chose *not* to do that, for a good reason:

A search can fail today simply because of a **temporary problem** — maybe the internet connection had a hiccup, or the online lookup service was briefly slow or blocked. That doesn't mean the place will *always* fail to be found. If we permanently remembered "this place failed," we might accidentally and permanently mark a real, valid place as "unresolvable" forever, just because of one bad moment.

To do this safely — remembering failures *but* being able to tell the difference between "this genuinely doesn't exist" and "this failed due to a temporary glitch" — you'd need a more complex system that tracks *when* something was last tried and automatically retries it after some time. That's a reasonable feature to build later, but for this competition-stage prototype, we made the honest, simpler choice: every failure gets a fresh, full attempt every single time. It costs a little bit of extra time on retries, but it guarantees we're never permanently and wrongly writing off a real place.

We call this out clearly as a **known limitation and a named area for future improvement** — not something we're hiding.

---

## PART 4 — THE TECHNOLOGY (Explained Without Assuming You're a Programmer)

### Q12. What are the main tools/technologies used, and what does each one actually do?

**Answer:**
Here's a plain-language breakdown of the tech stack — the set of tools used to build this:

| Tool Name | What it actually does, in plain words |
|---|---|
| **spaCy** | A ready-made AI tool that reads sentences and identifies things like "this word is a place name" — similar to how autocorrect on your phone knows the difference between a name and a regular word |
| **rapidfuzz** | A tool that compares two pieces of text and tells you how similar they are, even if they're spelled slightly differently — used to match "Bombay" with "Mumbai" or catch small typos |
| **GeoNames India** | A big, free, offline list of Indian place names along with their exact map coordinates, population, and region — like a giant printed atlas, except stored as data the computer can search instantly |
| **Nominatim** | A free online map-lookup service (similar in spirit to typing an address into Google Maps) used only as a backup, when our own offline database doesn't have the answer |
| **FastAPI** (Python) | The "engine" of the system — it's the part that receives the text, runs all the steps described earlier, and sends back the results. Written in Python, a common and reliable programming language |
| **Supabase (built on PostgreSQL)** | A database — basically an organized digital filing cabinet — where we store the place database, the "remembered" answers (caching), and a record of every report processed |
| **React + Vite** | The tools used to build the actual website/screen the user sees and interacts with |
| **React-Leaflet** | Adds the interactive map (the one with pins you can zoom and click) to the website, using free map tiles from OpenStreetMap |
| **Tailwind CSS** | A tool for styling the website quickly — making buttons, colors, and layout look clean without writing everything from scratch |

**In one sentence:** we picked entirely free, well-tested, widely-used tools — nothing requiring a paid subscription or a credit card — so the whole system can be built, run, and demoed without any risk of a paywall or a broken API key on demo day.

---

### Q13. Why did you choose these specific tools instead of alternatives?

**Answer:**
Every choice was made for a practical reason, not just because it's popular:

- **spaCy over building our own AI model from scratch:** Training your own AI to recognize place names would take enormous amounts of time and labeled data. spaCy already comes pre-trained and works well out of the box — no reason to reinvent this.

- **A local offline database (GeoNames India) instead of *only* relying on an online API:** Online services can be slow, rate-limited, or occasionally go down. Having our own local copy of Indian place data means most searches are instant and don't depend on the internet being fast or available at that exact moment.

- **Nominatim (free) instead of a paid mapping service like Google Maps:** Paid services need an API key (a kind of digital password) and a linked credit card, and can suddenly stop working if a limit is hit or a payment fails — a serious risk right before a live demo. Nominatim and OpenStreetMap need none of that, so there's zero risk of the demo breaking due to a billing issue.

- **Supabase instead of building our own database server from scratch:** Supabase gives us a ready-made, reliable, professionally-hosted database for free at our scale, saving weeks of setup work that would otherwise go into just keeping a database server running and secure.

- **React for the frontend instead of a simpler website:** Because the interface needs to update dynamically — highlighting text, updating the map, opening explanation panels when you click something — React is well-suited for building this kind of interactive, "living" interface, rather than a static page.

**Overall theme:** every choice minimizes risk (no paid services that could break the demo), while still being powerful enough to build something genuinely useful, not just a toy.

---

### Q14. What actual engineering difficulty is hidden behind this project? Isn't this just "call some APIs and glue them together"?

**Answer:**
It's fair to ask that, because on the surface, the pipeline (extract → clean → look up → decide → respond) sounds simple. But several genuinely tricky problems had to be carefully solved:

**Problem 1 — Deciding between multiple correct-looking answers.**
When a place name matches more than one real location, blindly picking "the biggest one" or "the first one found" is not good enough — and this is common because India has many towns and villages sharing names across different states. We had to design a weighted scoring formula that intelligently combines multiple signals (nearby places, region mentions, population) — and importantly, we had to decide *how much* to trust each signal relative to the others, and tune those numbers (like 70% one factor, 20% another, 10% the last) so the results actually make sense on real examples.

**Problem 2 — Never letting the "remembering" system store a wrong answer.**
If the caching system ever saved an incorrect answer, that mistake would then be served instantly, over and over, to every future request — a bad answer would spread and repeat itself rather than being a one-time mistake. We had to be very careful about *when* something gets remembered — only after it's gone through validation, and structured in a way where a bad entry can be found and fixed without corrupting other data.

**Problem 3 — Keeping results in the right order, even when some answers come back faster than others.**
Some place names get resolved almost instantly (because we already "remember" them), while others require a slower live lookup online. If we're not careful, the results could come back in a jumbled, unpredictable order — for instance, the *third* place name mentioned in a report might get its answer back before the *first* one does. But the analyst reading the results expects them in the same order the text was actually written. We had to build a system that separately tracks "where did this place name appear in the original sentence" and use that to correctly reorder the final answer — regardless of which one technically finished processing first.

**Problem 4 — Making sure one bad or unusual input never breaks everything.**
A single unresolvable name, or an empty submission, or unusual text shouldn't crash the whole system or return a broken response. Every edge case has to degrade gracefully — meaning it should still return something sensible and clearly explained, not an error message a normal user wouldn't understand.

These are the kinds of problems that don't show up if you just "call an API and print the result" — they only show up once you're trying to build something that has to be *correct*, *fast*, and *trustworthy* at the same time, which is a genuinely harder combination.

---

## PART 5 — HOW THE SYSTEM PROVES ITSELF (Feasibility, Testing, and Evidence)

### Q15. How do you know this actually works? What proof do you have?

**Answer:**
We have a live, working version of the system that anyone can test right now — not just a video or slides. The link is: **https://place-name-queries.vercel.app/**

Anyone — including a judge who has never seen our code — can go to that link, paste in a sentence describing an incident, and watch the system extract place names, resolve them, show them on a map, and explain its reasoning, live, in real time. This is the strongest kind of proof: it's not a claim, it's something you can try yourself.

Beyond that, we built a dedicated set of automated tests (checks that run the code and verify it behaves correctly) covering the "decision-making" part of the system (called `disambiguation.py`) and the part that assembles the final answer (`response_assembly.py`). These passed successfully, which gives confidence that the core logic behaves as intended, separate from whether the live database and internet connection are working at any given moment.

---

### Q16. Is this actually realistic to build and run, or is it just a hackathon prototype that would fall apart in the real world?

**Answer:**
We believe it's genuinely realistic, for a few concrete reasons:

**Nothing costs money to run:** every single tool used — the AI language model, the fuzzy-matching tool, the place database, the online fallback lookup, the map tiles — is completely free or open-source. There's no risk of the whole system suddenly breaking because a subscription expired or an API key ran out of free usage.

**The data is real, not fake:** we're using GeoNames India, which is a genuine, complete, publicly available dataset of real Indian places — not a small hand-typed sample list that only happens to work for the demo.

**The hard design decisions were made *before* writing code, not discovered by accident afterward:** Things like exactly how the caching should be structured, and exactly how the confidence-scoring formula should be weighted, were thought through, written down, and agreed on as a plan first. That's a sign of careful engineering, not last-minute patchwork.

**We're upfront about what still needs finishing:** as of the writing of our presentation, some parts (like final integration testing on a live, fully loaded database) are still being completed and verified — we don't claim things are done if they aren't. We treat this honestly as a work-in-progress heading toward the demo, not a project we're pretending is 100% finished and tested end-to-end when it isn't yet.

---

### Q17. What happens if this system needs to support way more people — say, 10,000 users at once? Does it fall apart?

**Answer:**
It wouldn't fall apart, and interestingly, it would actually get *more* efficient as usage grows, not less — because of the caching design explained earlier (Q10).

Here's the intuitive version: most place names that show up in Indian incident reports repeat a lot — major cities, well-known districts, common regions come up again and again across different reports. Every time a place name is looked up for the very first time, it costs some real time (checking the database, possibly querying the online fallback). But every *subsequent* time that same place name shows up — even in a completely unrelated report — the answer is already remembered and comes back almost instantly.

So the more the system is used, the higher the percentage of requests that get served instantly from memory, and the lower the percentage that need the slower, rate-limited online fallback. In other words: **the system's biggest potential bottleneck (the online service's strict 1-request-per-second limit) matters less and less as usage increases**, which is the opposite of how most systems behave (where more users usually means more strain).

We're upfront that this is currently an architectural expectation based on sound design, not yet something we've formally load-tested with thousands of simultaneous users — that kind of large-scale stress-testing is a reasonable next step beyond this hackathon prototype stage.

---

### Q18. What are the honest weaknesses or limitations of this system? Don't just tell me the good parts.

**Answer:**
We think it's important to be upfront about this rather than pretend the system is perfect. Here are real, acknowledged limitations:

1. **It only understands India-based place names.** As explained in Q8, this is intentional, but it does mean a report mentioning a place outside India will correctly, but perhaps unhelpfully, show up as "failed."

2. **It depends on the AI language tool correctly recognizing a word as a place name in the first place.** If the input text is very badly formatted, garbled, or uses an unusual style the AI model hasn't seen much of, it might miss a real place name entirely — and if it's never even recognized as a place, the rest of the system never gets a chance to look it up. We name this openly as a known boundary rather than hiding it.

3. **Failed lookups are never remembered/cached** (explained in Q11), which is the safer choice, but it does mean that if the exact same unresolvable name is submitted twice, the system will spend the same amount of time trying — and failing — both times, rather than instantly recognizing "we already know this one doesn't work."

4. **The online fallback service has a strict speed limit (1 request per second).** If many brand-new, never-before-seen place names all need the fallback search within the same request, there could be a noticeable delay while the system waits its turn to query that service one at a time.

5. **As of our current stage, formal, large-scale measured performance numbers (like exact response times or accuracy percentages under real production load) aren't finalized yet** — they depend on completing full end-to-end testing against a live, fully populated database, which is an active, ongoing part of our build process, not something we're claiming is already done.

We consider it more trustworthy — and frankly more professional — to state these limitations clearly, rather than present the system as flawless.

---

## PART 6 — WHY THIS IS DIFFERENT / BETTER (Innovation)

### Q19. Aren't there already tools that can find locations from text? What's actually new here?

**Answer:**
Yes, general-purpose place-name-finding tools already exist in the research world, and we studied several of them (referenced properly in our presentation with real academic sources). But most existing approaches have specific, documented weaknesses that our system was deliberately designed to address:

1. **"Popularity bias"** — many existing tools simply pick the most famous place with a matching name, ignoring context. Our system instead actively looks for nearby-place evidence and regional hints from the actual text, and only falls back to "pick the bigger place" as a last resort — and even then, flags that choice as lower-confidence.

2. **"No confidence check"** — many existing systems just hand you an answer with no indication of how sure they are. Ours always attaches a transparent confidence score and a written explanation.

3. **"India focus missing"** — most general geocoding research and tools are built with a global, one-size-fits-all mindset and aren't tuned specifically for the naming patterns and administrative structure found across India. Ours is deliberately India-first.

4. **"Slow repeated searches"** — as covered in Q10, many simple systems would re-query an external service every single time, hitting rate limits repeatedly. Our two-layer remembering system specifically solves this.

**In short:** the innovation isn't "we invented AI place-name recognition" — that groundwork already exists. The innovation is in **how thoughtfully we combined and adapted these existing building blocks** to specifically serve the real, documented weaknesses that analysts and researchers have already identified in this space — with India-specific tuning, honest confidence scoring, and a caching design that gets smarter the more it's used.

---

### Q20. If you had more time, what would you build next?

**Answer:**
A few honest, natural next steps:

1. **Smarter handling of failed lookups over time** — building the safer version of "remembering failures" mentioned in Q11, where a failure is remembered temporarily but automatically re-checked after some time, rather than either "never remember it" (current approach) or "remember it forever" (the risky approach we deliberately avoided).

2. **Support for messier, real-world text** — like reports with typos, unusual formatting, or text extracted from scanned documents, which can currently trip up the place-name-recognition step.

3. **Formal, large-scale performance testing** — actually measuring response times and accuracy under heavy simulated load, rather than relying on architectural reasoning about why it *should* scale well.

4. **Expanding beyond text-only input** — for example, being able to process reports that include images or PDFs, not just plain text.

We see these as natural, well-scoped next steps rather than signs that the current version is incomplete for its intended purpose — a working prototype for a hackathon demo that clearly shows the core idea works.

---

## QUICK-FIRE ROUND (Short Answers for Fast Back-and-Forth)

Use these for genuinely rapid one-liner exchanges, with the fuller explanation from above ready if the judge wants more detail.

| Question | Short Answer |
|---|---|
| What does the system take as input? | A piece of free-form text, like a report or alert. |
| What does it give as output? | A list of place names found, their map coordinates, a confidence score, and a plain-English reason for each. |
| Who is the target user? | Analysts and disaster-management operators — not everyday citizens. |
| Why India-only for the online fallback? | To avoid confidently pointing to the wrong country when a name is ambiguous. |
| What happens if a place can't be found? | It's honestly marked "failed" — never guessed. |
| What happens if no places are found at all? | The system says so clearly instead of returning an empty, unexplained result. |
| Why do some confidence scores get capped low? | Because population-only guesses are weak evidence and shouldn't look falsely certain. |
| What is "caching" here, in one line? | Remembering answers already worked out, so repeat questions are instant. |
| Why don't you cache failures? | A temporary glitch today doesn't mean the place is unresolvable forever. |
| What AI tool finds the place names? | spaCy, a pre-trained language-processing tool. |
| What handles spelling differences? | rapidfuzz, a fuzzy text-matching tool. |
| Where does the place data come from? | GeoNames India, a free, offline dataset of real Indian places. |
| What's the backup lookup service? | Nominatim, restricted to India-only results. |
| What's the single biggest design principle? | Be honest about uncertainty — never fake confidence. |
| Is this a citizen-facing app? | No — it's backend infrastructure for professional analysts. |
| Is everything free to run? | Yes — no paid APIs, no credit cards, no vendor lock-in. |
| Can you show it live right now? | Yes — https://place-name-queries.vercel.app/ |

---

**Document purpose:** Plain-English viva preparation companion — written so any reader, including someone outside the team, can understand the full "what, why, and how" of the project without prior context.
