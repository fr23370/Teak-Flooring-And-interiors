# Teak Flooring & Interiors website

## Run the website locally

Use Python 3.8 or newer. From this folder, run:

```powershell
python server.py
```

Open [http://localhost:8000](http://localhost:8000) to view the site, or
[http://localhost:8000/admin.html](http://localhost:8000/admin.html) to manage project photos.
The local gallery manager is available only from this computer.

## Manage project photos

The gallery manager lets you add project photos, update their title/category/description,
replace an image, or remove a photo. Supported formats are JPEG, PNG, WebP, and GIF,
up to 10 MB per image. Photos are saved in `images/projects/`; gallery entries are saved
in `data/projects.json`.

The gallery starts with clearly labeled design-inspiration photos. Replace these with
photos of completed Teak Flooring & Interiors projects before presenting them as portfolio
work.

## Hosting the website

The project gallery and upload manager require the Python server; a static-only file host
will not provide the upload API. For a remotely accessible server, set a unique strong
administrator password and configure HTTPS before starting the server:

```powershell
$env:TEAK_ADMIN_PASSWORD = "use-a-unique-strong-password"
$env:TEAK_HOST = "0.0.0.0"
$env:PORT = "8000"
python server.py
```

Place the server behind an HTTPS reverse proxy, forward the original `Host` and
`X-Forwarded-Proto` headers, and use storage that persists both `data/projects.json` and
`images/projects/` across restarts and deployments. Do not expose the upload manager over
plain HTTP or commit administrator passwords.
