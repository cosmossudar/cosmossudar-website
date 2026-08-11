# Cosmos Sudar — independent journalism website

Live at **[cosmossudar.com](https://cosmossudar.com)**. Built and run by Thirumalaiselvan.

> **New here? Open `START-HERE.html` in this folder.** It is the full setup and
> daily-use guide, written in plain language. This file is just the short version.

---

## How to publish a story

**Easiest:** open [pagescms.org](https://pagescms.org), sign in with GitHub, choose
this project, click **News Stories → Add new**, fill the form, hit Save.
The site rebuilds itself and the story is live in about a minute.

**Or by hand:** add a file to `content/news/` named `YYYY-MM-DD-short-title.md`.
Copy `content/news/_TEMPLATE.md` as your starting point.

```markdown
---
title: Your headline here
date: 2026-08-12
category: ground-report
location: Kanchipuram
image: /assets/uploads/photo.jpg
image_caption: What is in the photo. Photo: Thirumalaiselvan
summary: The one or two sentences people see on the front page and in WhatsApp previews.
tags: [water, panchayat]
draft: false
---

The story goes here, in ordinary paragraphs.
```

Sections available: `ground-report`, `civic`, `environment`, `politics`, `explainer`
— change or add to them in `site.json`.

Set `draft: true` to keep a story hidden while you write it.

---

## What is in this folder

| Path | What it is |
|---|---|
| `site.json` | Your name, tagline, email, WhatsApp, social links, sections. **The one file worth editing.** |
| `content/news/` | One markdown file per story. |
| `content/pages/` | The About and Ethics pages. |
| `assets/uploads/` | Photos used in stories. |
| `assets/css/style.css` | The whole design. |
| `build.py` | Turns the above into a website. Pure Python, no packages. |
| `.pages.yml` | Tells the free admin panel what the form should look like. |
| `.github/workflows/publish.yml` | Rebuilds and publishes on every change. |
| `_site/` | The generated website. Never edit this — it is overwritten each build. |

---

## Seeing it locally

Open `_site/index.html` in a browser — links are relative, so the whole site
browses correctly straight off the disk.

To rebuild after editing:

```bash
python3 build.py
```

Requires nothing but Python 3 — no packages, no `pip install`.
For the archive search box to work you need a real server:

```bash
cd _site && python3 -m http.server 8000   # then open http://localhost:8000
```

---

## Running costs

Nothing. GitHub Pages hosting, GitHub Actions builds and the Pages CMS admin panel
are all free for public repositories, with no trial period and no card on file.
The only thing paid for is the domain name itself.

## Why it is built this way

Every story is a plain text file in your own account. The site is plain HTML and CSS.
The build script uses only the Python standard library — nothing to install, nothing
that goes out of date, no framework to migrate off in three years.

If every service named here disappeared tomorrow, the folder would still contain a
complete, working website and every word ever published.
