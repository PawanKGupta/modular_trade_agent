# Kotak Neo REST API Usage

This document summarizes Kotak Neo APIs currently used by the project.

## Authentication (REST only)

- `POST https://mis.kotaksecurities.com/login/1.0/tradeApiLogin`
- `POST https://mis.kotaksecurities.com/login/1.0/tradeApiValidate`

The app stores:
- `baseUrl` (from validate)
- `token` as `Auth`
- `sid` as `Sid`

## Order APIs

- `POST {baseUrl}/quick/order/rule/ms/place`
- `POST {baseUrl}/quick/order/vr/modify`
- `POST {baseUrl}/quick/order/cancel`
- `POST {baseUrl}/quick/order/bo/exit`
- `POST {baseUrl}/quick/order/co/exit`

## Order Reports

- `GET {baseUrl}/quick/user/orders`
- `POST {baseUrl}/quick/order/history`
- `GET {baseUrl}/quick/user/trades`

## Portfolio & Account

- `GET {baseUrl}/quick/user/positions`
- `GET {baseUrl}/portfolio/v1/holdings`
- `POST {baseUrl}/quick/user/limits`
- `POST {baseUrl}/quick/user/check-margin`

## Quotes & Scrip Master

- `GET {baseUrl}/script-details/1.0/quotes/neosymbol/{query}[/{filter}]`
- `GET {baseUrl}/script-details/1.0/masterscrip/file-paths`

## Headers

- **Post-login APIs**: `Auth`, `Sid`, `neo-fin-key: neotradeapi`
- **Quotes/Scripmaster**: `Authorization: <access_token>` only

## Notes

- All SDK-based communication has been removed.
- Adapter and auth implementations are REST-only.

