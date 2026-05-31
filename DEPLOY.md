# Deploying MoneyMoney on Oracle Cloud (Always Free) + Tailscale

Goal: a $0, always-on server that runs the email poller 24/7, reachable privately from your
iPhone over Tailscale (no public ports, no domain, no TLS hassle). Data stays private.

Architecture:
```
iPhone (Tailscale) ──encrypted──► Oracle Always Free VM ──► Docker container
                                   (always on, poller runs)   FastAPI + PWA + SQLite (/data)
```

---

## Stage 1 — Oracle account + a free VM

1. Sign up at https://www.oracle.com/cloud/free/ .
   - **Pick your home region carefully — it's permanent.** Choose one near you
     (e.g. *Canada Southeast (Toronto)* or *(Montreal)*).
   - A credit card is required **only to verify identity**. Always Free resources don't charge.
   - ⚠️ Stay on **Always Free eligible** resources. Don't "Upgrade to Pay As You Go" unless
     you mean to.
2. Create the VM: console menu → **Compute → Instances → Create instance**.
   - **Image:** Canonical Ubuntu 22.04 (or 24.04).
   - **Shape:** click *Change shape* → pick an **Always Free eligible** shape:
     `VM.Standard.A1.Flex` (ARM, set 1 OCPU / 6 GB) if available, else `VM.Standard.E2.1.Micro`.
   - **Networking:** keep the default (creates a VCN, assigns a public IPv4).
   - **SSH keys:** choose *Generate a key pair*, then **download the private key** (`.key`).
   - Click **Create**, wait for **Running**, copy the **Public IP address**.
3. From your Mac, test SSH (Ubuntu's default user is `ubuntu`):
   ```bash
   chmod 400 ~/Downloads/your-key.key
   ssh -i ~/Downloads/your-key.key ubuntu@<PUBLIC_IP>
   ```

## Stage 2 — Install Docker + Tailscale on the VM

```bash
# Docker
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER && newgrp docker

# Tailscale (free; gives the VM a private 100.x IP reachable by your devices)
curl -fsSL https://tailscale.com/install.sh | sh
sudo tailscale up        # opens a login URL; sign in with the SAME account you'll use on iPhone
tailscale ip -4          # note the 100.x.x.x address
```

## Stage 3 — Get the code onto the VM and run it

Recommended: push this repo to a **private GitHub repo**, then on the VM:
```bash
git clone https://github.com/<you>/moneymoney.git
cd moneymoney
docker build -t moneymoney .
```

Run it (binds to the Tailscale IP only — never the public internet):
```bash
sudo mkdir -p /opt/moneymoney-data
docker run -d --name moneymoney --restart unless-stopped \
  -p $(tailscale ip -4):8000:8000 \
  -v /opt/moneymoney-data:/data \
  -e GMAIL_ADDRESS="you@gmail.com" \
  -e GMAIL_APP_PASSWORD="xxxx xxxx xxxx xxxx" \
  -e APP_USERNAME="me" \
  -e APP_PASSWORD="<long random password>" \
  moneymoney
```

> Secrets are passed as env vars here. They live only on your VM, never in git.

## Stage 4 — Use it on your iPhone

1. Install **Tailscale** from the App Store; sign in with the same account; toggle it on.
2. In Safari, visit `http://<VM-tailscale-100.x.x.x>:8000`.
3. Enter the Basic-auth username/password (APP_USERNAME / APP_PASSWORD).
4. Share → **Add to Home Screen**. It now behaves like an app.

## Redeploying (e.g. after the RBC parser lands)

```bash
cd moneymoney && git pull && docker build -t moneymoney . \
  && docker rm -f moneymoney && docker run -d ... (same run command as above)
```

## Notes

- The poller runs inside the container 24/7, so transactions are captured even when your
  phone/laptop is off.
- Because access is Tailscale-only, the app isn't exposed to the public internet; Basic auth
  is a second layer.
- SQLite lives in `/opt/moneymoney-data` on the VM — back it up by copying that folder.
