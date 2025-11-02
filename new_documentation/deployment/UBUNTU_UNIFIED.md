# Ubuntu Unified Service — Quick Steps

Recommended production deployment on Ubuntu/Debian.

Install (systemd)
```bash
sudo nano /etc/systemd/system/tradeagent-unified.service
```
Paste:
```ini
[Unit]
Description=Trade Agent (Unified) - Continuous Trading Service
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=YOUR_USERNAME
Group=YOUR_USERNAME
WorkingDirectory=/home/YOUR_USERNAME/modular_trade_agent
ExecStart=/home/YOUR_USERNAME/modular_trade_agent/.venv/bin/python /home/YOUR_USERNAME/modular_trade_agent/modules/kotak_neo_auto_trader/run_trading_service.py --env modules/kotak_neo_auto_trader/kotak_neo.env
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal
Environment="PATH=/home/YOUR_USERNAME/modular_trade_agent/.venv/bin:/usr/local/bin:/usr/bin"
NoNewPrivileges=true
PrivateTmp=true

[Install]
WantedBy=multi-user.target
```
Enable & start
```bash
sudo systemctl daemon-reload
sudo systemctl enable tradeagent-unified.service
sudo systemctl start tradeagent-unified.service
```

More details
- Full guide: documents/deployment/ubuntu/INSTALL_UBUNTU.md (Unified Service section)
- Services overview (advanced): documents/deployment/ubuntu/SERVICES_COMPARISON.md
