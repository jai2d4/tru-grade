# YouTube link downloads

If a link fails with *"Sign in to confirm you're not a bot"*, nothing is
wrong with your film, your link, or the app. YouTube is refusing to serve
an anonymous download to a server. They have been tightening this
steadily, and it affects every tool that fetches YouTube video.

## The short answer

**Upload the file directly instead.** It always works, it is faster (no
download step), and the quality is better — YouTube re-encodes what you
upload, so a link round-trip analyses a degraded copy of your own film.

The link path exists for one reason: it was a workaround for a hosting
platform that rejected large uploads. Running TruGrade on your own
machine, that limit is gone (`MAX_UPLOAD_MB`, default 2048).

So use links for convenience when they work, and reach for direct upload
the moment they don't.

## What the app already tries

Before failing, the download is retried as several different YouTube
clients (android, ios, tv_embedded, web_safari). YouTube challenges these
inconsistently, so a block on one often isn't a block on all. Override
the order with `YTDLP_PLAYER_CLIENTS` if you find one that works reliably
for you.

## Making links work reliably: sign the server in

A signed-in request usually clears the challenge. Two ways.

### Option A — read cookies from a browser on the same machine

Simplest if the app runs on a desktop where you're signed into YouTube:

```
YTDLP_COOKIES_FROM_BROWSER=chrome
```

Accepts `chrome`, `firefox`, `edge`, `brave`, `chromium`, `safari`,
`opera`, `vivaldi`. The browser must be installed and logged in as a user
that can watch the video. Close the browser first — some lock their
cookie database while running.

### Option B — an exported cookie file

Needed on a headless machine:

1. In a browser signed in to YouTube, install a "Get cookies.txt"
   extension.
2. Export cookies for `youtube.com` while on a YouTube page.
3. Copy the file to the machine running TruGrade and point at it:

```
YTDLP_COOKIE_FILE=/path/to/cookies.txt
```

**Treat that file as a password.** It carries a live session for the
account that exported it — anyone holding it can act as that account.
Keep it readable only by the account running the app, keep it out of
version control, and use a throwaway YouTube account rather than a
personal one.

Cookies also expire. When links start failing again after working,
re-export before assuming something broke.

## Keeping yt-dlp current

YouTube changes its defences often, and yt-dlp responds in days. A
version that is months old is a common cause of sudden failures:

```
pip install --upgrade yt-dlp
```

`requirements.txt` pins a version deliberately, so builds are
reproducible. Bump the pin, run the tests, and commit both together
rather than upgrading in place and leaving the pin lying.

## What won't help

- **Retrying the same link repeatedly.** The challenge is not transient;
  each attempt costs time and makes the block more likely to stick.
- **A different link to the same video.** The challenge is about the
  requester, not the URL.
- **Making the video public.** Public videos are challenged too. (Private
  and members-only videos fail for a different, real reason — the server
  genuinely cannot see them. Unlisted works.)
