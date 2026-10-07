# Zendesk Help Center -> Confluence Cloud Migrator

A reusable Python tool for migrating a Zendesk Help Center **category** into an **existing Confluence Cloud space**.

The migration keeps a local HTML/ZIP backup, recreates Zendesk sections as Confluence pages, uploads images and attachments, and rewrites links between migrated Zendesk articles so they point to their new Confluence pages.

> **Start here:** [Download the ZIP and run it](#download-the-zip-and-run-it). You do not need Git. You do not need to understand the REST APIs.

---

# Download the ZIP and run it

Use this path when someone sends you the project, or when you download it from GitHub. Keep the unzipped folder intact. Do not pull out a single file.

## 1. Download and unzip

Downloading the ZIP is not enough. The tools only run after the ZIP has been unzipped into a normal folder.

1. Open https://github.com/Dav418/zendesk-article-to-html
2. Click the green **Code** button.
3. Click **Download ZIP**.

Direct link to the ZIP:

https://github.com/Dav418/zendesk-article-to-html/archive/refs/heads/main.zip

### Unzip on a Mac

1. Open **Downloads**.
2. Double-click `zendesk-article-to-html-main.zip`.
3. A folder named `zendesk-article-to-html-main` appears next to the ZIP.
4. Open that folder. You should see `start.command` in the list. If you only see the ZIP, it is not unzipped yet.

### Unzip on Windows

1. Open **Downloads**.
2. Right-click `zendesk-article-to-html-main.zip`.
3. Choose **Extract All**, then **Extract**.
4. Open the new folder. Keep opening folders until you see `start.bat`.
5. Do not double-click `start.bat` from the window that opens when you click the ZIP itself. That window has not unzipped the files, and the migration will not work from there.

## 2. Install Python

The tool needs **Python 3.11 or newer**. Check before installing anything else.

### Mac

1. Open **Terminal** (search for Terminal in Spotlight).
2. Paste this and press Return:

   ```bash
   python3 --version
   ```

3. If you see `Python 3.11` or a higher 3.x number, skip the installer.
4. If the command is not found, or the version is older than 3.11, download the macOS installer from https://www.python.org/downloads/macos/
5. Open the downloaded `.pkg` and accept the defaults.
6. Close Terminal, open it again, and run `python3 --version` once more.

### Windows

1. Open **Command Prompt** (search for `cmd`).
2. Paste this and press Enter:

   ```bat
   py -3 --version
   ```

3. If you see `Python 3.11` or a higher 3.x number, skip the installer.
4. Otherwise download the Windows installer from https://www.python.org/downloads/windows/
5. Run the installer. On the first screen, tick **Add python.exe to PATH**, then choose **Install Now**.
6. Close Command Prompt, open it again, and run `py -3 --version` once more.

## 3. Fill in `.env`

The migration reads one settings file, named `.env`. An empty `.env`, or one that still has example values such as `you@company.com` or `PASTE_ZENDESK_TOKEN_HERE`, will not run. The [setup checklist](#setup-checklist) lists every value. Zendesk needs one login and Confluence needs one login: email plus API token, or OAuth client ID plus secret. Leave the login you are not using blank.

The file sits in the unzipped folder, next to `start.command` and `start.bat`. It is not inside `.venv`.

The first time the start script runs, it creates `.env` from `.env.example` if `.env` is missing or empty, then opens it. You still have to replace the example values and save.

### Find `.env` on a Mac

Finder hides the file because the name starts with a dot.

1. Open the unzipped folder in Finder.
2. Press **Command + Shift + .** (the period key). Hidden files appear in grey. `.env` is one of them.
3. Double-click `.env`. If Mac asks which app to use, choose **TextEdit**.
4. Replace the example values. The [setup checklist](#setup-checklist) says where each value comes from.
5. Save the file.
6. Press **Command + Shift + .** again to hide those files.

`.venv` is a different hidden folder. Do not edit anything inside it.

### Find `.env` on Windows

The file is in the same folder as `start.bat`.

1. Open that folder in File Explorer.
2. If you do not see `.env`, click **View**, then **Show**, and tick **File name extensions** and **Hidden items**.
3. Double-click `.env`, or let `start.bat` open it in Notepad.
4. Replace the example values. The [setup checklist](#setup-checklist) says where each value comes from.
5. Choose **File → Save**.

After `.env` is saved, run the start script again.

## 4. Run the migration

The start script installs the small Python libraries this folder needs, then runs `migrate.py`.

`migrate.py` does four things:

1. Downloads the whole Zendesk category onto this computer. It does this once. Later runs reuse that download.
2. Checks Confluence without creating pages. If the space, parent page, or a title is wrong, it stops here.
3. Uploads the **first 5 articles** and asks you to look at them.
4. If you type `yes`, it uploads the rest in groups of 50. Each group includes the articles already uploaded and adds the next ones. It does not replace the earlier pages.

If Confluence asks the tool to slow down, it waits and continues. If the run stops because the network dropped, run the same start script again. Finished articles are left as they are.

Type anything other than `yes` after the first 5 to stop. The rest are not uploaded. Run the start script again later and type `yes` when you want the rest.

### Mac

Double-click `start.command` in Finder. If macOS says it cannot be opened or cannot be verified, click **Done** (not Move to Bin). Then open **System Settings → Privacy & Security**, scroll down to the message about `start.command`, click **Open Anyway**, and confirm. On older macOS versions, right-click the file, choose **Open**, and confirm instead.

If that does not open a useful window, open Terminal, type `bash ` (with the space), drag `start.command` from Finder into the Terminal window, and press Return.

### Windows

In the unzipped folder, double-click `start.bat`. If Windows shows **Windows protected your PC**, click **More info**, then **Run anyway**.

If the window says the ZIP was not unzipped, close it, use **Extract All** as described above, and double-click `start.bat` in that new folder.

If the window closes immediately, open Command Prompt, `cd` into the unzipped folder, and run:

```bat
start.bat
```

## 5. When it stops on a real problem

A normal pause after the first 5 is not a failure. These are failures:

- `.env` is missing, empty, or still has example values
- Zendesk or Confluence rejects the login (`401`) or the permissions (`403`)
- the Confluence space or parent page is wrong
- a page title in the space already matches an article that would be created
- the Zendesk download itself failed

The window prints what to fix. A technical log is written to `output/migration-error.log` inside the unzipped folder. Fix the problem, then run the start script again.

---

## Setup checklist

Before running anything, collect these values. Zendesk needs **one** login. Confluence needs **one** login. Fill in either the email and API token, or the OAuth client ID and secret. Leave the other login blank.

| Value | Example | Where it comes from |
| --- | --- | --- |
| Zendesk category URL | `https://company.zendesk.com/hc/en-gb/categories/123456-category-name` | Open the category you want to migrate and copy the browser URL |
| Confluence base URL | `https://company.atlassian.net` | Your normal Confluence site address, without `/wiki/spaces/...` |
| Confluence space key | `OPS` | The text after `/spaces/` in the space URL. See section 4.4 |
| Confluence parent page ID | `123456789` | The number after `/pages/`, or **••• → Page information** and the `pageId=` number. See section 4.5 |

Zendesk login. Use one row pair, not both.

| Login | Values | Where they come from |
| --- | --- | --- |
| Email and API token | `ZENDESK_EMAIL` and `ZENDESK_API_TOKEN` | Your Zendesk login email, and a token an admin creates. See section 2.3 |
| OAuth client | `ZENDESK_OAUTH_CLIENT_ID` and `ZENDESK_OAUTH_CLIENT_SECRET` | Admin Center → Apps and integrations → APIs → OAuth clients. Copy the Identifier and Secret. See section 2.4 |

Confluence login. Use one row pair, not both.

| Login | Values | Where they come from |
| --- | --- | --- |
| Email and API token | `CONFLUENCE_EMAIL` and `CONFLUENCE_API_TOKEN` | The email you use for Atlassian, and an API token you create. See section 4.3 |
| OAuth client | `CONFLUENCE_OAUTH_CLIENT_ID` and `CONFLUENCE_OAUTH_CLIENT_SECRET` | Atlassian Administration → Directory → Service accounts → Create credentials → OAuth 2.0. See section 4.7 |

### Keep the secrets secret

- Never paste an API token or an OAuth client secret into a ticket, chat, email, screenshot, or commit.
- Put secrets only in your local `.env` file.
- `.env` is already ignored by Git in this repo.
- The example values in `.env.example` are placeholders only.
- After the migration is finished and checked, revoke the API tokens or OAuth clients you used if they are no longer needed.

---

# 1. Install by hand

Skip this section if you ran `start.command` or `start.bat`. Those scripts create the Python environment and install the libraries for you.

## macOS / Linux

Open Terminal in the repo folder and run:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
cp .env.example .env
```

## Windows PowerShell

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
Copy-Item .env.example .env
```

You will now have a local file called `.env`. That is the file you edit with the real URLs and one login each for Zendesk and Confluence. See the [setup checklist](#setup-checklist).

---

# 2. Zendesk: get the source URL and credentials

## 2.1 Get the Zendesk category URL

Open the Zendesk Help Center category that contains the articles you want to migrate.

The URL should look like:

```text
https://company.zendesk.com/hc/en-gb/categories/123456-category-name
```

Copy the **whole URL** and put it in `.env`:

```env
ZENDESK_CATEGORY_URL=https://company.zendesk.com/hc/en-gb/categories/123456-category-name
```

You do not need to manually copy the category ID or locale. The script extracts both from the URL.

This migration is category-scoped: it fetches all articles returned for that category and follows Zendesk pagination automatically.

## 2.2 Important: Messaging keys are NOT the right credentials

If an existing application has values such as:

```text
ZENDESK_KEY_ID
ZENDESK_SECRET
```

or a Zendesk Messaging `channelKey` / `channelId`, **do not use them here**.

Those belong to Zendesk Messaging/end-user authentication. They do not authenticate this script to the Zendesk Help Center API.

## 2.3 Easiest option: Zendesk API token

For this option you need:

```text
Your normal Zendesk email
+
A Zendesk API token
```

### If you are NOT a Zendesk admin

You cannot create this token yourself. Ask a Zendesk admin to create one.

You can send them this exact message:

> Hi, I need to export our Zendesk Help Center content through the Zendesk Help Center API for a one-off Confluence migration. Could you please create a temporary Zendesk API token named **Zendesk Confluence migration** and share the token with me using our normal secure credential-sharing method? The script only reads Zendesk. I will authenticate as my own Zendesk user, so my existing Zendesk permissions still apply. The token can be deactivated/deleted after the migration.

The admin does **not** need to give you their Zendesk password or their own account credentials.

### Instructions for the Zendesk admin

1. Sign in to Zendesk as an administrator.
2. Open **Admin Center**.
3. Go to **Apps and integrations -> APIs -> API configuration**.
4. Make sure **Allow API token access** is enabled. If it is already enabled, leave it enabled.
5. Go to **Apps and integrations -> APIs -> API tokens**.
6. Click **Add API token**.
7. Enter a description such as:

   ```text
   Zendesk Confluence migration
   ```

8. Click **Save** to generate the token.
9. **Copy the full token immediately and store/share it securely.** Zendesk does not show the full token again after the token window is closed.
10. Do not send the token in an ordinary email/chat if your company has a password manager or other approved secret-sharing method.

Official Zendesk instructions:

- https://support.zendesk.com/hc/en-us/articles/8662004958746-Turning-on-and-off-API-access
- https://support.zendesk.com/hc/en-us/articles/4408889192858-Managing-API-token-access-to-the-Zendesk-API

### Put the Zendesk credentials in `.env`

Use **your own normal Zendesk login email**, not the admin's email:

```env
ZENDESK_EMAIL=you@company.com
ZENDESK_API_TOKEN=PASTE_THE_ZENDESK_TOKEN_HERE
ZENDESK_OAUTH_CLIENT_ID=
ZENDESK_OAUTH_CLIENT_SECRET=
```

Do **not** add `/token` to your email. The script does that internally. Leave the two OAuth lines blank when you use email + API token. If `ZENDESK_OAUTH_CLIENT_ID` and `ZENDESK_OAUTH_CLIENT_SECRET` are both filled in, those are used instead and the email and API token are ignored.

Why is the email needed? A Zendesk API token is account-level rather than belonging to one user. Your email identifies which verified Zendesk user is making the request, so Zendesk applies that user's permissions.

### Zendesk API-token retirement

Zendesk is retiring this authentication method. As of October 2026:

- existing eligible accounts can still create API tokens until **27 October 2026**;
- after that date, new API-token creation is blocked;
- existing active API tokens are scheduled to stop working on **30 April 2027**.

That is fine for this short-lived migration, but do not build a permanent integration around a new API token.

Official announcement:

https://support.zendesk.com/hc/en-us/articles/10840968198042-Announcing-the-removal-of-API-tokens-as-an-authentication-method-for-API-requests

## 2.4 Zendesk OAuth alternative

If your company will not provide an API token, an admin creates an OAuth client and you put its Identifier and Secret in `.env`. The script asks Zendesk for an access token itself. You do not run a separate command.

1. In Admin Center, open **Apps and integrations → APIs → OAuth clients**.
2. Click **Add OAuth client**. Name it `Zendesk Confluence migration`. Set **Client kind** to **Confidential**. Leave **Redirect URLs** empty. Allow the **hc:read** scope.
3. Click **Save**. Copy the **Identifier** and the **Secret**. Zendesk shows the full secret only once.

```env
ZENDESK_OAUTH_CLIENT_ID=the-identifier
ZENDESK_OAUTH_CLIENT_SECRET=the-secret
ZENDESK_EMAIL=
ZENDESK_API_TOKEN=
```

On export, the script sends those two values to Zendesk and uses the access token Zendesk returns. The token lasts 48 hours, which is the longest Zendesk allows.

This token acts as the Zendesk admin who created the OAuth client. That admin must be able to see the category, including any restricted articles you want exported. If that admin is later removed or loses admin rights, the login stops working. The email + API token route still works: leave the Identifier and Secret blank and fill in `ZENDESK_EMAIL` and `ZENDESK_API_TOKEN` instead.

Official Zendesk OAuth documentation:

https://developer.zendesk.com/documentation/authentication/creating-and-using-oauth-tokens-with-the-api/

---

# 3. Export Zendesk locally

Fill in `.env` before the first command. Zendesk needs one login, and Confluence needs one login. For each, fill in either the email and API token, or the OAuth client ID and secret. Leave the other login blank. You do not fill in both.

Export checks that file too, so a missing login stops it. The export itself only reads Zendesk and writes files to your computer. It does not change anything in Confluence.

Run:

```bash
python main.py export
```

A successful export creates a workspace similar to:

```text
output/
└── zendesk-category-123456/
    ├── manifest.json
    ├── migration-report.csv
    ├── migration-report.json
    ├── Category Name-confluence-import.zip
    └── html/
        └── Category Name/
            ├── Category Name - Index.html
            ├── Section - Accounts.html
            ├── Article name.html
            └── Article name/
                ├── screenshot.png
                └── form.pdf
```

The ZIP is retained as a backup/alternative even if you use the direct Confluence uploader.

If `export` fails with `401 Unauthorized`, re-check the Zendesk login you filled in: the email and API token, or the OAuth client Identifier and Secret. If it fails with `403 Forbidden`, that login may not have permission to read the requested content.

---

# 4. Confluence: get the target and credentials

You need an **existing Confluence Cloud space** and an **existing parent page** inside that space. The migration will be created underneath that parent page.

This repo needs these Confluence values:

```text
1. Confluence base URL
2. Space key
3. Parent page ID
4. ONE login:
   - your Atlassian email + an Atlassian API token (sections 4.2 and 4.3), or
   - an OAuth client ID + secret (section 4.7)
```

With the email + API token login you do **not** need to be a Confluence admin. Your account does need permission to view the target space, create/edit pages below the target parent, and upload attachments. The OAuth client login needs an organisation admin to create it, and the service account needs the same space permissions.

## 4.1 Get the Confluence base URL

Open Confluence normally.

If a page looks like:

```text
https://company.atlassian.net/wiki/spaces/OPS/pages/123456789/Knowledge+Base
```

then your base URL is:

```env
CONFLUENCE_BASE_URL=https://company.atlassian.net
```

You can also paste a base URL ending in `/wiki`; the script normalises it. Using the plain site URL is simplest.

## 4.2 Get your Confluence email

Use the email address for the Atlassian account you normally use to sign in to Confluence:

```env
CONFLUENCE_EMAIL=you@company.com
```

This does not need to match the Zendesk email, although for many companies it will.

## 4.3 Create the Atlassian API token

Go directly to:

https://id.atlassian.com/manage-profile/security/api-tokens

Sign in with the same Atlassian account that can edit the target Confluence space.

Then:

1. Click **Create API token**.
2. For **this version of the repo, choose the normal `Create API token` option, not `Create API token with scopes`**.
3. Give it a clear name, for example:

   ```text
   Zendesk Confluence migration
   ```

4. Choose a short expiry. Around 30 days is sensible for a one-off migration.
5. Click **Create**.
6. Click **Copy to clipboard**.
7. Store the token securely. Atlassian will not show the full token again later.
8. Put it in `.env`:

   ```env
   CONFLUENCE_API_TOKEN=PASTE_THE_ATLASSIAN_TOKEN_HERE
   ```

Official Atlassian token page/documentation:

- https://id.atlassian.com/manage-profile/security/api-tokens
- https://support.atlassian.com/atlassian-account/docs/manage-api-tokens-for-your-atlassian-account

### Why not choose a scoped token?

Atlassian recommends scoped tokens where possible. Scoped tokens use a different API hostname and require a Confluence Cloud ID. This version of the repo deliberately uses the simpler site-specific Confluence REST URL and therefore expects a **standard/unscoped Atlassian API token** when using email + token authentication.

If your organisation will not allow a standard API token, use the OAuth client ID and secret in section 4.7 instead.

Official Confluence authentication documentation:

https://developer.atlassian.com/cloud/confluence/basic-auth-for-rest-apis/

## 4.4 Get the Confluence space key

Open the space where the migration should live.

A URL commonly looks like:

```text
https://company.atlassian.net/wiki/spaces/OPS/overview
```

or:

```text
https://company.atlassian.net/wiki/spaces/OPS/pages/123456789/Knowledge+Base
```

The value immediately after `/spaces/` is the **space key**.

For the examples above:

```env
CONFLUENCE_SPACE_KEY=OPS
```

Do not put the whole URL into `CONFLUENCE_SPACE_KEY`.

## 4.5 Choose the parent page and get its page ID

The parent page is the existing Confluence page that all migrated pages will be created underneath. The page ID is a number. It is not the page title and not the space key.

### Make a page to use as the parent

Create an empty page such as `Zendesk import` and use that as the parent. Everything the tool creates then sits in one place, and a test run is easy to delete.

1. Open the space while logged in.
2. In the left sidebar, under **Content**, click **+** (or the **Create** button next to the space name).
3. Type the title, for example `Zendesk import`. Leave the body empty.
4. The sidebar shows the new page with a grey **Draft** label. A draft has no page ID yet, and the migration cannot use it.
5. Click **Publish** at the top right. If it asks where to put the page, leave the location as the space home page.
6. After publishing, the **Draft** label disappears. Now read the page ID with one of the ways below.

### Way 1: read it from the address bar

If the page address contains `/pages/`, the number straight after `/pages/` is the page ID:

```text
https://company.atlassian.net/wiki/spaces/OPS/pages/123456789/Knowledge+Base
                                                    ^^^^^^^^^
                                                    page ID
```

```env
CONFLUENCE_PARENT_PAGE_ID=123456789
```

### Way 2: the address has no number (for example a space overview page)

A space's home page often has an address like `https://company.atlassian.net/wiki/spaces/OPS/overview`, with no number in it.

1. Open the page in Confluence while logged in.
2. Click the **•••** button (More actions) at the top right of the page, next to Share.
3. Click **Page information**. On some sites it is under **Advanced details**, then **Page information**.
4. The address bar now contains `pageId=` followed by a number, for example `.../pages/viewinfo.action?pageId=123456789`.
5. Copy only the digits after `pageId=` into `CONFLUENCE_PARENT_PAGE_ID`.

### Check it

`preflight` checks that the page exists and is in the space set in `CONFLUENCE_SPACE_KEY`. Nothing is uploaded. If the ID is wrong, preflight stops and says so.

In this example the resulting structure will be approximately:

```text
Knowledge Base                         <- existing parent page 123456789
└── Zendesk category name             <- created by this tool
    ├── Section A
    │   ├── Article 1
    │   └── Article 2
    └── Section B
        └── Article 3
```

The tool does not replace or delete the existing parent page.

## 4.6 Put the Confluence values in `.env`

The normal setup is:

```env
CONFLUENCE_BASE_URL=https://company.atlassian.net

CONFLUENCE_EMAIL=you@company.com
CONFLUENCE_API_TOKEN=PASTE_THE_ATLASSIAN_TOKEN_HERE
CONFLUENCE_OAUTH_CLIENT_ID=
CONFLUENCE_OAUTH_CLIENT_SECRET=

CONFLUENCE_SPACE_KEY=OPS
CONFLUENCE_PARENT_PAGE_ID=123456789

CONFLUENCE_CREATE_CATEGORY_ROOT=true
CONFLUENCE_ROOT_PAGE_TITLE=
CONFLUENCE_EXISTING_TITLE_POLICY=fail
CONFLUENCE_UPLOAD_DRAFTS=false
CONFLUENCE_RESTRICTED_ARTICLE_POLICY=warn
```

Leave `CONFLUENCE_ROOT_PAGE_TITLE` blank unless you specifically want the new top-level migration page to have a different name. Blank means: use the real Zendesk category name. Leave the two OAuth lines blank when you use email + API token. If both OAuth lines are filled in, those are used and the email and API token are ignored.

## 4.7 Confluence OAuth client

This is the same idea as the Zendesk OAuth client. An organisation admin creates it, and the script asks Atlassian for an access token. You do not fetch or paste that token.

1. Open [Atlassian Administration](https://admin.atlassian.com/).
2. Go to **Directory → Service accounts**.
3. Open the service account, or create one, then choose **Create credentials → OAuth 2.0**.
4. Under **Confluence scopes**, select these four scopes:

   - `read:confluence-space.summary` — read the target space;
   - `read:confluence-content.all` — read the parent and existing pages;
   - `write:confluence-content` — create and update pages;
   - `write:confluence-file` — upload attachments.

   The names shown by Atlassian may be friendlier descriptions such as **Read Confluence space summary**, **Read Confluence content**, **Write Confluence content**, and **Upload Confluence attachments**. Do not select delete-space or delete-content permissions; this tool does not need them.
5. Copy the **client ID** and **client secret**. Atlassian shows the secret only once.
6. Give the service account access to the target space. A service account is not a member of any space by default. In Confluence, open the space, then **Space settings → Users** (or **Permissions**), add the service account, and allow it to view the space, add pages, and add attachments. Without this, preflight fails with `403 Forbidden`.

```env
CONFLUENCE_OAUTH_CLIENT_ID=the-client-id
CONFLUENCE_OAUTH_CLIENT_SECRET=the-client-secret
CONFLUENCE_EMAIL=
CONFLUENCE_API_TOKEN=
```

The access token lasts about an hour. The script fetches a new one when it is about to expire. To use email + API token instead, leave the client ID and secret blank.

Official Atlassian instructions:

https://support.atlassian.com/user-management/docs/create-oauth-2-0-credential-for-service-accounts/

Official Confluence scope list:

https://developer.atlassian.com/cloud/confluence/scopes-for-oauth-2-3LO-and-forge-apps/

---

# 5. Complete `.env` example

This is what a normal one-off migration configuration looks like. **Replace every example value with your own value.**

```env
# -----------------------------------------------------------------------------
# Zendesk source
# -----------------------------------------------------------------------------
ZENDESK_CATEGORY_URL=https://company.zendesk.com/hc/en-gb/categories/123456-category-name

ZENDESK_EMAIL=you@company.com
ZENDESK_API_TOKEN=PASTE_ZENDESK_TOKEN_HERE
ZENDESK_OAUTH_CLIENT_ID=
ZENDESK_OAUTH_CLIENT_SECRET=

# -----------------------------------------------------------------------------
# Local export
# -----------------------------------------------------------------------------
OUTPUT_DIR=output
INCLUDE_DRAFTS=true
ALLOW_PARTIAL_EXPORT=false
FAIL_ON_UNRESOLVED_ZENDESK_LINKS=false
REQUEST_TIMEOUT_SECONDS=30
ARTICLE_LIMIT=

# -----------------------------------------------------------------------------
# Confluence target
# -----------------------------------------------------------------------------
CONFLUENCE_BASE_URL=https://company.atlassian.net

CONFLUENCE_EMAIL=you@company.com
CONFLUENCE_API_TOKEN=PASTE_ATLASSIAN_TOKEN_HERE
CONFLUENCE_OAUTH_CLIENT_ID=
CONFLUENCE_OAUTH_CLIENT_SECRET=

CONFLUENCE_SPACE_KEY=OPS
CONFLUENCE_PARENT_PAGE_ID=123456789

CONFLUENCE_CREATE_CATEGORY_ROOT=true
CONFLUENCE_ROOT_PAGE_TITLE=
CONFLUENCE_EXISTING_TITLE_POLICY=fail
CONFLUENCE_UPLOAD_DRAFTS=false
CONFLUENCE_RESTRICTED_ARTICLE_POLICY=warn
```

Never commit the completed `.env` file.

---

# 6. Run the migration

`migrate.py` (started by `start.command` or `start.bat`) is the normal way to run this. It downloads the category, checks Confluence, uploads 5 articles, waits for you to type `yes`, then uploads the rest in groups of 50.

The commands below are the same steps, run one at a time. Use them when you want to control each batch yourself. Run them from the project folder with the `.venv` from section 1 active. On a Mac without it active, `python` may not exist or may not have the libraries; use `.venv/bin/python main.py ...` instead. On Windows, use `.venv\Scripts\python.exe main.py ...`. `export`, `preflight`, and `upload` use the same Python 3.11 check and the same `.env` check as `start.command` and `start.bat`: a missing, empty, or example `.env` stops the command and explains how to find the file.

The migration is deliberately split into three commands so you do not accidentally create hundreds of Confluence pages while merely testing credentials.

## Try a small batch first

Do not upload the whole category on the first run. Start with **5 articles** and open those Confluence pages. That check is about how the pages look, not about a request limit.

Confluence does not block you at a fixed article count. With the email + API token login, it blocks short bursts of requests and usually clears within seconds. With the OAuth client login, Atlassian can also apply an hourly request allowance, so a big upload may be asked to wait longer. Either way this tool waits when Confluence asks it to, then continues. Pages already created are saved. If an upload stops anyway, run the same `upload --yes` command again. Finished articles are not copied again. If an earlier article links to a page that did not exist yet, the next batch updates that link so it points at the new Confluence page.

`--limit` keeps the first N articles, in section order and then article order, and leaves the rest untouched. On upload, drafts do not count toward that number unless `CONFLUENCE_UPLOAD_DRAFTS=true`. Only the sections that contain the selected articles, plus their parent sections, are created. After the first 5 pages look right, use a larger limit, such as 50, or omit `--limit` for the rest.

Export the category once, then upload a handful of articles and check them in Confluence:

```bash
python main.py export
python main.py preflight --limit 5
python main.py upload --limit 5 --yes
```

When those pages look right, raise the limit. Pages already created are reused, so the next run adds the following articles instead of copying the first ones. Links in the earlier articles are updated to those new pages:

```bash
python main.py preflight --limit 50
python main.py upload --limit 50 --yes
```

Omit `--limit` when you are ready for the rest:

```bash
python main.py preflight
python main.py upload --yes
```

`--limit` on `export` is only for avoiding a full download. A limited export replaces the local manifest with that smaller set, so run a full `python main.py export` before the real migration. Prefer a full export and `--limit` on `preflight` / `upload`.

You can also set `ARTICLE_LIMIT` in `.env`. A `--limit` on the command replaces it for that run. Leave `ARTICLE_LIMIT` blank to mean "every article".

A later run with a smaller limit does not delete pages from the larger run. It also rewrites the section and category index pages in that smaller batch so they list only the current batch. Use the same limit, or a larger one, when you continue.

## Step 1 - Export everything from Zendesk

```bash
python main.py export
```

This command:

- reads Zendesk;
- exports every matching article returned for the selected category;
- downloads article attachments and inline images;
- records Zendesk sections/hierarchy;
- produces the local manifest/reports;
- creates a Confluence-compatible HTML ZIP backup;
- **does not write anything to Confluence**.

Check the summary and `migration-report.csv` before continuing.

## Step 2 - Run Confluence preflight

```bash
python main.py preflight
```

This is **read-only** against Confluence. It creates no pages and uploads no attachments.

It checks:

- whether your Confluence credentials work;
- whether the configured space exists;
- whether the parent page exists and belongs to that space;
- existing page-title conflicts;
- how many sections/articles are planned;
- draft handling;
- Zendesk restricted-article warnings;
- existing resume state from a previous interrupted migration.

The detailed result is saved to:

```text
output/zendesk-category-123456/confluence-preflight.json
```

Do not continue to upload until preflight succeeds and the target looks correct.

## Step 3 - Upload to the existing Confluence space

Only after preflight succeeds:

```bash
python main.py upload --yes
```

`--yes` is required deliberately because this command writes to Confluence.

The uploader then:

1. creates the category root page, if enabled;
2. recreates Zendesk section pages in parent/child order;
3. creates all article pages with temporary placeholder bodies;
4. records every new Confluence page ID/URL;
5. uploads each article's images/files as Confluence attachments;
6. rewrites migrated Zendesk article/section/category links to the new Confluence destinations;
7. updates the article bodies;
8. populates the section/index pages.

Creating the pages before rewriting the bodies is what allows article A to link correctly to article B even when article B did not exist in Confluence before the migration.

A later batch does the same for articles uploaded earlier. Their files are not uploaded again. Their page text is updated so a link that still pointed at Zendesk now points at the Confluence page created in this batch.

---

# 7. What the migration creates

With the recommended settings:

```text
Existing Confluence space
└── Existing parent page                    <- you choose this
    └── Zendesk category name               <- tool creates this
        ├── Section A
        │   ├── Article 1
        │   └── Article 2
        └── Section B
            ├── Nested section
            │   └── Article 3
            └── Article 4
```

If:

```env
CONFLUENCE_CREATE_CATEGORY_ROOT=false
```

then the section pages are created directly beneath your existing parent page. In that mode the script does not edit the existing parent page.

---

# 8. Link handling

For an original Zendesk link such as:

```text
https://company.zendesk.com/hc/en-gb/articles/987654-how-to-upload-a-document
```

if article `987654` is part of this migration, the final Confluence content points to the newly-created Confluence page instead of the old Zendesk page.

The tool handles:

- article -> migrated article;
- article -> migrated section;
- article -> migrated category;
- links in section/category descriptions;
- `#fragment` anchors;
- Zendesk attachment links;
- inline Zendesk images;
- externally hosted inline images successfully downloaded during export.

Normal external links are not changed.

If a Zendesk link points to an article outside the selected category, it is left unchanged and recorded in the migration report rather than guessed.

---

# 9. Images and attachments

Zendesk article attachments are downloaded during `export`.

During direct Confluence upload, each file is attached to the corresponding Confluence article page. Image elements are converted to Confluence attachment-image markup and ordinary attachment links are converted to Confluence attachment links.

The final Confluence pages therefore do not need Zendesk to remain online in order to display migrated images/files that were successfully exported.

---

# 10. Drafts and restricted Zendesk articles

## Drafts

Local export defaults to:

```env
INCLUDE_DRAFTS=true
```

so the backup contains drafts that your Zendesk account can access.

Direct Confluence upload defaults to:

```env
CONFLUENCE_UPLOAD_DRAFTS=false
```

because a Zendesk draft uploaded with the normal Confluence page API would become a normal published Confluence page.

If you explicitly set:

```env
CONFLUENCE_UPLOAD_DRAFTS=true
```

the draft is uploaded as a normal Confluence page with a visible `Zendesk status: Draft` marker.

## Restricted articles

Zendesk user-segment restrictions do not automatically translate into equivalent Confluence restrictions.

Default:

```env
CONFLUENCE_RESTRICTED_ARTICLE_POLICY=warn
```

The migration can continue, but preflight/reports warn you that restricted Zendesk pages will inherit the destination Confluence hierarchy's permissions.

For a stricter migration:

```env
CONFLUENCE_RESTRICTED_ARTICLE_POLICY=fail
```

Preflight then blocks the upload while restricted Zendesk articles are present.

---

# 11. Existing Confluence title conflicts

Confluence page titles need to be unique within the target space for the API flow used here.

Recommended/default:

```env
CONFLUENCE_EXISTING_TITLE_POLICY=fail
```

If a required title already exists on a live page elsewhere in the space, preflight fails **before anything is created**. An archived or draft page also reserves its title. In that case the new page is given a Zendesk suffix and the upload continues.

If you prefer automatic safe renaming:

```env
CONFLUENCE_EXISTING_TITLE_POLICY=suffix
```

For example:

```text
Opening an account
```

may become:

```text
Opening an account (Zendesk article-123456)
```

Duplicate titles inside the migration itself are also made unique when necessary.

---

# 12. Resume behaviour

`--limit` uses this same state file. A later upload with a higher limit creates the additional articles and reuses pages from the smaller run.

Once an upload starts, the tool creates:

```text
output/zendesk-category-123456/confluence-upload-state.json
```

It records the Confluence page IDs, titles and URLs created by this migration. It contains **no API tokens**.

Do not delete this file after a partial upload. It is what lets a rerun continue using already-created pages instead of creating another copy of everything. If you change the Confluence space, the parent page, or whether the category page is created, the next run removes this file itself and starts a new upload. Pages already created in Confluence are left where they are.

On rerun, the tool also checks that pages recorded in state still exist and have not been manually renamed. If they have changed, it stops rather than blindly overwriting that manual change.

The tool is deliberately non-destructive. If an article later disappears from Zendesk, an old Confluence page recorded in state is not automatically deleted.

There is intentionally no automated delete/rollback command.

---

# 13. Reports

After `export`:

```text
migration-report.csv
migration-report.json
manifest.json
```

After `preflight`:

```text
confluence-preflight.json
```

After `upload --yes`:

```text
confluence-upload-report.csv
confluence-upload-report.json
confluence-upload-state.json
```

The upload report includes the Zendesk article ID, original title, final Confluence title, Confluence page ID/URL, asset counts and link-rewrite counts.

---

# 14. Common problems

## Zendesk: `401 Unauthorized`

The error says which login was used.

If it was the email + API token:

- `ZENDESK_EMAIL` is your real verified Zendesk login email, for an agent or admin;
- `ZENDESK_API_TOKEN` contains the token and has no accidental spaces;
- you did not put `/token` onto the email yourself;
- the token is still active, and **Allow API token access** is on in Admin Center;
- `ZENDESK_OAUTH_CLIENT_ID` and `ZENDESK_OAUTH_CLIENT_SECRET` are blank. If both are filled in, the email and API token are not used.

If it was the OAuth client:

- `ZENDESK_OAUTH_CLIENT_ID` is the client **Identifier**, and `ZENDESK_OAUTH_CLIENT_SECRET` is the full secret;
- the client kind is **Confidential** and it allows the `hc:read` scope;
- the admin who created the client still has admin rights.

## Zendesk: `403 Forbidden`

Authentication may be valid but the login may not have permission to see the category/article. With email + API token, Zendesk uses your user's permissions. With the OAuth client, it uses the permissions of the admin who created the client.

## Zendesk: I only have `ZENDESK_KEY_ID` and `ZENDESK_SECRET`

Those are normally Zendesk Messaging credentials. They are not Help Center API credentials. Ask a Zendesk admin for the API/OAuth access described above.

## Zendesk: admin cannot see `Add API token`

Possible reasons include account policy or Zendesk's API-token retirement. Use Zendesk OAuth instead. From **27 October 2026**, Zendesk says new Support API-token creation is blocked for everyone.

## Confluence: still limiting requests

The upload waits and retries when Confluence answers "too many requests". If it still stops, wait the number of minutes it prints and run the same command again:

```bash
python main.py upload --limit 5 --yes
```

Use the same `--limit` as the run that stopped. Pages already created are reused, and articles that already finished are not uploaded again. A later, larger batch still updates links in those earlier articles when the page they point at has been created.

## Confluence: `401 Unauthorized`

The error says which login was used.

If it was the email + API token:

- `CONFLUENCE_EMAIL` is the Atlassian account that created the token;
- you copied the full token when it was created;
- the token has not expired/revoked;
- you created the standard **Create API token** token, not the scoped-token variant;
- `CONFLUENCE_OAUTH_CLIENT_ID` and `CONFLUENCE_OAUTH_CLIENT_SECRET` are blank. If both are filled in, the email and API token are not used.

If it was the OAuth client:

- the client ID and full client secret were copied from the service account's **OAuth 2.0** credential;
- the credential has not been revoked;
- it has the four Confluence scopes listed in section 4.7.

## Confluence: `403 Forbidden`

Authentication can be correct while the login lacks permission. With the OAuth client, check that the service account was added to the space (section 4.7, step 6). Confirm the account you are using can:

- view the target space;
- view the chosen parent page;
- create and edit pages there;
- upload attachments.

## Confluence: wrong space or parent page

Do **not** run `upload --yes`. Correct:

```env
CONFLUENCE_SPACE_KEY=...
CONFLUENCE_PARENT_PAGE_ID=...
```

and rerun:

```bash
python main.py preflight
```

Preflight is specifically there to catch this before the script creates pages.

---

# 15. After the migration

Once you have checked the Confluence pages, links and attachments:

1. keep the local export/reports somewhere appropriate for your migration records;
2. revoke the Confluence login you used: the Atlassian API token, or the service-account OAuth credential;
3. ask the Zendesk admin to revoke the Zendesk login you used: the API token, or the OAuth client;
4. do not leave `.env` sitting in an insecure shared folder;
5. never commit `.env` to source control.

A Zendesk admin removes an API token under **Admin Center → Apps and integrations → APIs → API tokens**, or an OAuth client under **OAuth clients** on that same APIs page.

For an Atlassian API token, revoke it here:

https://id.atlassian.com/manage-profile/security/api-tokens

---

# 16. Tests

Install dev dependencies and run:

```bash
pip install -r requirements-dev.txt
python -m pytest -q
```

---

# Relevant API documentation

Zendesk:

- Help Center articles: https://developer.zendesk.com/api-reference/help_center/help-center-api/articles/
- Sections: https://developer.zendesk.com/api-reference/help_center/help-center-api/sections/
- Article attachments: https://developer.zendesk.com/api-reference/help_center/help-center-api/article_attachments/
- Zendesk API authentication: https://support.zendesk.com/hc/en-us/articles/4408831452954-How-can-I-authenticate-API-requests
- Zendesk API-token management: https://support.zendesk.com/hc/en-us/articles/4408889192858-Managing-API-token-access-to-the-Zendesk-API
- Zendesk API-token retirement: https://support.zendesk.com/hc/en-us/articles/10840968198042-Announcing-the-removal-of-API-tokens-as-an-authentication-method-for-API-requests
- Zendesk OAuth client credentials: https://developer.zendesk.com/documentation/authentication/creating-and-using-oauth-tokens-with-the-api/

Confluence / Atlassian:

- Atlassian API-token management: https://support.atlassian.com/atlassian-account/docs/manage-api-tokens-for-your-atlassian-account
- Confluence basic auth: https://developer.atlassian.com/cloud/confluence/basic-auth-for-rest-apis/
- Atlassian service-account OAuth credentials: https://support.atlassian.com/user-management/docs/create-oauth-2-0-credential-for-service-accounts/
- Confluence REST examples: https://developer.atlassian.com/cloud/confluence/rest-api-examples/
- Confluence attachment API: https://developer.atlassian.com/cloud/confluence/rest/v1/api-group-content---attachments/
