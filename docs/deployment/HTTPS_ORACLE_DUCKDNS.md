# HTTPS on Oracle VM (DuckDNS)

Production host: **https://reboundsignals.duckdns.org**

## Layout

```text
Internet :443/:80
  → host nginx (Ubuntu, Let's Encrypt)
  → http://127.0.0.1:5173 (Docker tradeagent-web, container nginx)
       → /api/* proxied to tradeagent-api:8000
```

Host config: `/etc/nginx/sites-available/reboundsignals`  
Certificate: `/etc/letsencrypt/live/reboundsignals.duckdns.org/` (auto-renew via certbot timer)

## (Re)issue certificate

```bash
sudo certbot --nginx -d reboundsignals.duckdns.org
sudo nginx -t && sudo systemctl reload nginx
```

Non-interactive (first-time style):

```bash
sudo certbot --nginx -d reboundsignals.duckdns.org \
  --non-interactive --agree-tos --register-unsafely-without-email --redirect
```

## Razorpay

| Setting | Value |
|---------|--------|
| Website | `https://reboundsignals.duckdns.org` |
| Webhook | `https://reboundsignals.duckdns.org/api/v1/billing/webhooks/razorpay` |

## DuckDNS

If the VM public IP changes, update the `reboundsignals` A record at [duckdns.org](https://www.duckdns.org) before HTTPS breaks.

## Firewall (OCI)

Inbound **TCP 80** and **443** must be allowed on the instance security list / NSG.
