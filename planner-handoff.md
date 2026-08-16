# Planner Artifact — Operating Rules

**Governs:** `planner.html` (single self-contained HTML file, ~2300 lines)
**Tooling:** `planner_tools.py` (validation, state dump)
**Published:** GitHub Pages — `git push` to `huixin96f/Todo` auto-deploys `planner.html`
**Last updated:** 2026-08-16

This is the rules file for the planner artifact. Any session that edits, updates, or
controls `planner.html` must read this file first and follow it. Rules are numbered so
they can be cited (`R3.2`, `R5.1`) in conversation.

---

## 0. Starting cold — read this first

This folder is self-contained. A new session, in any AI harness, needs nothing but the
folder and this file.

**Do this before touching anything:**

```bash
python3 planner_tools.py state      # what the list currently holds
python3 planner_tools.py validate   # confirm it parses and has no duplicates
```

`state` prints the live data, the earliest pending day, and the next free code for every
prefix. **It is the only trustworthy snapshot** — this document deliberately hardcodes no
task data, because a written snapshot goes stale within a day (see `R2.1` and §8).

Then read §2 (the edit loop you must follow on every request), §3 (hard rules), and §6
(what the user's phrasing means). §10 covers the phone copy and the one thing you cannot
derive from the folder: the published URL.

Requirements: `python3` and `git` only. No `node`, no packages, no network, no build
system. Publishing is `git push` (§10) — no other step.

**The user does not write code.** They direct in chat — usually in Chinese, sometimes
English — and review the result visually. Never hand them a script to run, never ask them
to edit a file or check a value themselves. Do it, verify it, and show them the outcome.

---

## 1. What this artifact is

A personal daily task planner. One self-contained HTML file — no backend, no database,
no build step. All task data is hardcoded as JavaScript arrays near the top of the
`<script>` block. **The file itself is the database.**

**R1.1 — The workflow is chat-driven.** The user issues task-management commands in chat
(bilingual Chinese/English). The assistant edits the arrays inside `planner.html`
directly, validates, and hands the updated file back.

**R1.2 — Do not add persistence.** No localStorage, no auto-save, no backend. The user
has already declined these; they understand each download creates a new file copy and
prefer the tell-the-assistant-to-edit workflow. Do not re-propose it.

---

## 2. The edit loop — required every time

Every request that touches task data follows this loop, in this order:

**R2.1 — Read and parse, never assume.** Load the current arrays from the file before
deciding anything. Never act on remembered state, including state written in §8 of this
document.

**R2.2 — Batch the whole request into one script run.** A multi-part request ("mark T5
done, add two tasks, move X to the top") is one script, one validation, one handback —
not three rounds.

**R2.3 — Validate before handing back.** Run the validator (`R3.2`). Only hand back the
file when it prints `All checks passed.`

**R2.4 — Always show BOTH the artifact and the website after any change.** ⚑
Whenever `planner.html` changes — a task added, edited, completed, reordered, moved
between panels, or deleted, **and** any structural, CSS, or JS edit — the reply that
reports the change must contain **both** of these. Never describe a change without
showing the result.

| # | What to show | How |
|---|--------------|-----|
| 1 | **The artifact** — `planner.html` itself, rendered inline | Whatever the harness uses to display a local file in chat. In Claude Code: `SendUserFile` on `planner.html` with `display: "render"` |
| 2 | **The website** — the live published URL | The `R10.1` link, written out in full as a clickable link |

If the harness genuinely cannot render a local file inline, **say so in the reply** and
attach or link the file instead. Silently dropping half of this rule is the failure mode
it exists to prevent.

- Show both **after** validation passes and after the push in `R2.6`, never before —
  the link must already point at the new state when the user taps it.
- One of each per reply, even when the reply batches many changes.
- This applies to every change, however small. There is no "too minor to show."
- Showing only one of the two is a rule violation, not a shortcut.

**R2.5 — Confirm briefly in text alongside the render.** A short line plus the resulting
order — not a wall of explanation. See §9.

**R2.6 — Commit and push after every change.** Every change also updates the phone
version, in the same reply, so it can never silently go stale:

```bash
python3 planner_tools.py validate   # R3.2 — never commit a broken file
git add planner.html
git commit -m "…"
git push                            # GitHub Pages auto-deploys (§10)
```

Publishing is `git push` and nothing else — the site rebuild takes a minute or two.
**If the push fails, do not skip it silently:** finish the edit, validate, show the file,
and tell the user plainly that the phone copy is now behind and needs a successful push.
A stale phone copy the user believes is current is worse than a reported failure.

---

## 3. Hard rules

### R3.1 — Never translate titles
Store task titles **exactly** as the user typed them — Chinese stays Chinese, English
stays English, mixed stays mixed. Never add a translated note, never "clean up" the
wording. Only real reference information (phone numbers, URLs, addresses) goes in `note`.

### R3.2 — Mandatory validation after every edit
This machine has no `node`, only `/usr/bin/python3`. Run:

```bash
python3 planner_tools.py validate
```

It checks that `EVENTS`, `POOL`, and `LONGTERM` all parse, and that `EVENTS` and `POOL`
contain no duplicate codes. Hand back the file only on `All checks passed.`

This rule exists because of real failures: missing trailing commas broke the file twice,
and stale leftover blocks created duplicate entries (T22/T24/P6/T21 once; F8/F9 once).
The user explicitly asked for **both** syntax and duplicate checks. See Appendix A for
the original `node` version if working on a machine that has it.

### R3.3 — Always edit via script, never by hand
Read → parse → mutate → serialize → write back. `planner_tools.py` exports the two helpers:

```python
import json, re
from planner_tools import grab, parse_js_array

html = open('planner.html', encoding='utf-8').read()
events = parse_js_array(grab(html, 'EVENTS'))

# ... mutate events ...

ev_str = 'const EVENTS = ' + json.dumps(events, ensure_ascii=False, indent=2) + ';'
html = re.sub(r'const EVENTS = \[[\s\S]*?\];', lambda m: ev_str, html, count=1)
open('planner.html', 'w', encoding='utf-8').write(html)
```

Two gotchas, both load-bearing:
- `ensure_ascii=False` — without it every Chinese title becomes `\uXXXX` escapes.
- Pass the replacement to `re.sub` as a **lambda**, so `\1`-style sequences inside task
  titles aren't interpreted as backreferences.

String-replace editing of individual array entries repeatedly failed because of
whitespace drift. Use the script pattern.

### R3.4 — Never announce a change you didn't make
Verify with a script rather than asserting from memory. If something failed, say so
plainly — a duplicate-write bug happened once, and the right response was to catch it in
validation, clean it up, and report it.

---

## 4. Data model

Three arrays live near the top of the script block:

| Array | Panel | Contents |
|-------|-------|----------|
| `EVENTS` | Calendar + "Other Scheduled Tasks" | Date-assigned items |
| `POOL` | "To Schedule" | Unscheduled items, no date |
| `LONGTERM` | "Long-term" | No deadline, no code |

### Item shapes

```js
// EVENTS item
{ code: "T101", category: "Task", title: "公司给个人转账",
  date: "2026-07-30", status: "Pending", order: 0 }

// EVENTS item, completed
{ code: "T56", category: "Task", title: "准备父亲贷款",
  date: "2026-07-30", status: "Done", order: 101,
  doneAt: "2026-07-30 12:50" }

// POOL item (no date, no order)
{ code: "T10", category: "Task", title: "Google Maps spa booking link",
  note: "如牛兵卫 waitlist + Google reviews: shop.tapfive.com, Clover, Cluster",
  status: "Pending" }

// LONGTERM item (no code, no category, no date)
{ title: "property insurance", status: "Pending" }
{ title: "联系senneville septic tank", note: "4504587016 ext.216 — ...", status: "Pending" }
```

**R4.1 — Field rules**
- `order` (int) controls within-day display order for Pending items, starting at 0.
- `doneAt` format is `"YYYY-MM-DD HH:MM"` — only present on Done items.
- `note` is optional; used only for genuine reference info (phone numbers, URLs).

**R4.2 — Preserve serialization format.** `EVENTS` and `POOL` are stored as
`JSON.stringify(…, null, 2)` output — quoted keys, multiline. Keep that format.
`LONGTERM` is a hand-aligned JS object literal with unquoted keys; `parse_js_array()`
handles both.

### R4.3 — Categories and colors

```js
const CAT = {
  "Meeting":   {color:"#3B5BDB", light:"#dbe4ff"},   // prefix M
  "Call":      {color:"#0CA678", light:"#c3fae8"},   // prefix C
  "Review":    {color:"#E67700", light:"#fff3bf"},   // prefix R
  "Task":      {color:"#7048E8", light:"#e5dbff"},   // prefix T
  "Follow-up": {color:"#A61E4D", light:"#ffdeeb"},   // prefix F
  "Site Visit":{color:"#1971C2", light:"#d0ebff"},   // prefix S
  "Personal":  {color:"#2F9E44", light:"#d3f9d8"},   // prefix P
};
```

**R4.4 —** `LONGTERM` items have no category, so `.lt-card` renders on a plain white
background. **This is intentional, not a bug** — the user asked about it and chose to
leave it.

---

## 5. Codes and ordering

### R5.1 — Code counters
Codes are `<PREFIX><N>`, prefix from the category. **Retired codes are never reused, and
gaps are never filled.** The next code for a prefix is `highest number ever issued + 1`,
cross-checked against the retired list — *not* the first unused number. Scanning only
live codes finds a gap where a retired code used to be and silently reissues it; that
happened on 2026-07-31 and was caught in review.

**Do not read the next code from a table — compute it.** `python3 planner_tools.py state`
prints the next free code for every prefix, derived from the live data plus the retired
list below, so it cannot drift. The table is a convenience copy only:

| Prefix | Category | Next |
|--------|----------|------|
| T | Task | **T115** |
| P | Personal | **P50** |
| F | Follow-up | **F12** |
| M | Meeting | **M5** |
| S | Site Visit | **S4** |
| C | Call | **C1** |
| R | Review | **R2** |

Deleted/retired codes (do not reuse): F1, F3, P4, P7, P12, P42, T16, T20, T25, T43,
T89, T98, R1.

> **F4 was previously listed as retired here in error.** It is a live `Done` record dated
> 2026-06-25, still in `EVENTS`. Verified against the data and removed from the list on
> 2026-07-31. Every other code on the list was confirmed absent from `EVENTS` and `POOL`.

**R5.2 — When a code is retired, add it to the retired list in BOTH places:** the list
below and the `RETIRED` set in `planner_tools.py`. That set is what makes `state` compute
the next code correctly. The convenience table above can be refreshed from `state` at any
time; the retired list cannot be derived from anything and is the one thing that must be
written down.

### R5.3 — Done-item ordering
- When marking Done: set `status:"Done"`, `order` to **100+**, and `doneAt`.
- Use the next free 100+ number for that date (100, 101, 102, …) so nothing collides
  with Pending orders.
- Done items are sorted **by `doneAt` ascending**, not by `order` — the 100+ value only
  guarantees they sort after Pending.

### R5.4 — Renormalize after every removal
After removing an item from a day's Pending list — completed, deleted, moved, or
reordered — renormalize the remaining Pending orders on that date to `0..n-1`.

---

## 6. Standard command patterns

The user's phrasing repeats. These are the recurring operations.

**R6.1 — Daily rollover**
> "今天是 X 月 X 日，把之前没做完的任务都移到今天" / "Today is July Xth. Move whatever is
> not done from previous days to today."

Find all `status:"Pending"` with `date < today`, sort by `(date, order)`, move each to
today's date, and append **after** any items already scheduled for today (preserving
their existing orders), assigning sequential orders.

**R6.2 — Move to top**
> "把 X 移到最前面" / "Move X to the top"

Pull the named item(s) out of today's Pending list, put them at the front **in the order
the user listed them**, renormalize.

**R6.3 — Insert relative to another item**
> "把 X 放在 Y 之后" / "Add Z before T3"

Splice into the Pending array at the right index, then renormalize.

**R6.4 — Add a task**
> "今天加一项，X"

Append at `max(order)+1` unless the user says "放在最前面" / "at the top", in which case
insert at 0 and shift the rest. Default date is today unless a date is named ("明天",
"这周五", "8 月 2 日").

**R6.5 — Mark done**
> "T57 于 22:30 做完" / "T71 finished at 15:25"

Set Done + 100+ order + `doneAt` (`R5.3`). If the user names a **past** date ("T91
finished at 22:10 on 2026.07.29"), also change `date` back to that date.

**R6.6 — Add an already-completed task**
> "今天加一项，健身。已于 22 点做完。"

Create it directly with `status:"Done"` and the given `doneAt` — it never appears as
Pending.

**R6.7 — Merge two tasks**
> "合并 T97 和 T98 成一项"

Keep the lower code, join the titles with `、`, retire the other code.

**R6.8 — Delete**
> "删除 T20"

Filter it out of the array entirely, retire the code, renormalize that day.

---

## 7. Features already built — do not regress

**R7.1 — Treat this list as a regression checklist.** Any structural, CSS, or JS edit
must leave all of the following intact.

- **Unified calendar grid** — day labels and cells share one CSS grid:
  `grid-template-columns:repeat(7,minmax(0,1fr))`. The `minmax(0,...)` is load-bearing:
  plain `1fr` lets long titles widen columns unequally.
- **Chip truncation** — `.ev-chip` is `display:block; width:100%; max-width:100%` with
  `white-space:nowrap; overflow:hidden; text-overflow:ellipsis`. Cells carry
  `overflow:hidden`.
- **Max 3 chips per cell**, then a `+N more` line, then P/D mini-stat badges.
- **Today cell styling** — light `#eef2ff` background, 2px `#3B5BDB` border ring, blue
  date number. Renders normal chips like any other day. *(Earlier iterations used a dark
  `#1a1a2e` fill; with many items the semi-transparent chips stacked into an unreadable
  black block. Do not go back to a dark fill.)*
- **Day panel with separated sections** — Pending cards on top; then a divider reading
  `已完成 N`; then Done cards, greyed at 0.7 opacity with strikethrough titles and a
  `✓ <doneAt>` line.
- **Sort function** — `eventsForDate()` sorts Pending before Done regardless of `order`
  value, Pending by `order`, Done by `doneAt`:
  ```js
  function eventsForDate(k){
    return EVENTS.filter(e=>e.date===k).sort((a,b)=>{
      if(a.status!==b.status) return a.status==='Pending'?-1:1;
      if(a.status==='Pending') return (a.order??99)-(b.order??99);
      return (a.doneAt||'').localeCompare(b.doneAt||'');
    });
  }
  ```
- **"Other Scheduled Tasks"** (renamed from "Scheduled") — lists all Pending dated events
  **except** the currently selected day's. `renderScheduled()` must be called inside both
  `selectDay()` and `closePanel()`, otherwise the filter silently doesn't apply.
- **Drag & drop** — cross-date / pool / longterm moves plus within-day reorder with a
  blue insert line.
- **Mobile long-press drag** — touch drag activates only after a 300 ms hold
  (`LONG_PRESS_MS`), cancelled if the finger moves more than 6 px (`LONG_PRESS_SLOP`).
  This is what lets normal swipes scroll the page instead of grabbing a card. A
  `.drag-activating` pulse animation gives feedback.
- **Swipe left/right on the calendar** changes month — min 50 px horizontal, max 80 px
  vertical drift, and ignores touches that start on a draggable card.
- **Month + year dropdown selectors** at the top, synced with the `‹` `›` arrow buttons.
- **Responsive breakpoint** `@media (max-width:700px)` — single column, right panel
  stacks below the calendar, smaller cells and fonts.
- **Auto-select today on load** — `init()` computes today's key and calls
  `selectDay(todayKey)` so the day panel opens on today automatically.

---

## 8. Current data state

**There is deliberately no snapshot here.** An earlier version of this document carried
one and it was days out of date within a day of being written — exactly the trap `R2.1`
warns about. Get the live state instead:

```bash
python3 planner_tools.py state
```

It prints totals, the earliest pending day (roll it forward first — `R6.1`), every other
scheduled day, the pool, the long-term list, and the next free code per prefix. Run it at
the start of a session and any time you need to orient.

---

## 9. Communication rules

**R9.1 — Confirm briefly.** A short line plus the resulting order, alongside the rendered
HTML (`R2.4`) — not a wall of explanation.

**R9.2 — Infer obvious typos, ask about real ambiguity.** Typos are frequent ("题 21" =
T21, "家一项" = 加一项, "作完" = 做完, "机箱" = 几项, "Move as one" = Move S1). Infer the
obvious ones and say what you assumed. Ask when a code or a time is genuinely missing.

**R9.3 — Report failures plainly.** If validation fails or an edit went wrong, say so and
what you did about it.

**R9.4 — Keep this file current.** When the user establishes a new standing instruction,
add it here as a numbered rule in the same reply. When a code is retired, update both
places named in `R5.2`.

**R9.5 — Reply in the language the user used.** They write mostly Chinese, sometimes
English, often mixed. Match them. Task titles are never translated either way (`R3.1`).

**R9.6 — The user does not program.** They direct and review visually; they do not read
code, run commands, or inspect files. Never end a reply with something for them to
execute or verify. Do the work, check it yourself, and show the result.

---

## 10. Phone access — the published site

The user reads the planner on their phone at:

**`https://huixin96f.github.io/Todo/planner.html`**

**R10.1 — Publishing is `git push`, nothing else.** The public repo `huixin96f/Todo`
(main branch, root path) auto-deploys to GitHub Pages; the URL above is permanent and
must never change. Never mint a different URL for this planner.

**R10.2 — Serve `planner.html` itself, never `.build/`.** `.build/planner-artifact.html`
was a shim for the old claude.ai artifact host — nested-head workaround, viewport
re-rooting, region-specific ASCII escaping. GitHub Pages serves the source file directly
(it carries its own `<meta charset>` and viewport), so the derived file is obsolete for
publishing and is gitignored. Do not reintroduce it.

**R10.3 — On the phone it is a viewer.** Drag/reorder works in the session but nothing
persists on reload, exactly as on desktop (`R1.2`). Task changes still go through chat.

**R10.4 — The site and repo are PUBLIC.** The user chose a public repo on 2026-08-16
(GitHub Free cannot run Pages on a private one). The page contains family loan details,
CRA tax amounts, and phone numbers — anyone with the link, or the repo, can see them.
Never suggest sharing the link. Never push any other private content into this repo.

**R10.5 — Migration history.** 2026-08-16: migrated from a private claude.ai artifact
URL to GitHub Pages, per the standard migration flow (PAT with Contents + Administration
write, repo made public, Pages enabled from main, `.nojekyll` added). The old URL
`https://claude.ai/code/artifact/2d28a417-…` is dead; do not republish to it.

---

## Appendix A — `node` validator

For machines that have `node`, equivalent to `R3.2`:

```bash
node -e "
const fs = require('fs');
const html = fs.readFileSync('planner.html', 'utf8');
const eventsMatch = html.match(/const EVENTS = (\[[\s\S]*?\]);/);
const poolMatch   = html.match(/const POOL = (\[[\s\S]*?\]);/);
const ltMatch     = html.match(/const LONGTERM = (\[[\s\S]*?\]);/);
let ok = true;
['EVENTS','POOL','LONGTERM'].forEach((name,i)=>{
  const m=[eventsMatch,poolMatch,ltMatch][i];
  try{eval(m[1]);console.log(name+' syntax: OK');}
  catch(e){console.log(name+' SYNTAX ERROR:',e.message);ok=false;}
});
let events; eval('events = '+eventsMatch[1]);
const codes=events.map(e=>e.code);
const dupes=codes.filter((c,i)=>codes.indexOf(c)!==i);
if(dupes.length===0)console.log('EVENTS duplicates: none');
else{console.log('EVENTS DUPLICATES:',[...new Set(dupes)].join(', '));ok=false;}
let pool; eval('pool = '+poolMatch[1]);
const poolCodes=pool.map(e=>e.code);
const poolDupes=poolCodes.filter((c,i)=>poolCodes.indexOf(c)!==i);
if(poolDupes.length===0)console.log('POOL duplicates: none');
else{console.log('POOL DUPLICATES:',[...new Set(poolDupes)].join(', '));ok=false;}
console.log(ok?'\nAll checks passed.':'\nFIX REQUIRED.');
"
```

The `node` version `eval`s `LONGTERM` directly; the Python version normalizes unquoted
keys and trailing commas first. Both accept the same file.
