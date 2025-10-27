# Telegram Notifications on GCP

## ✅ Yes, Telegram Works on GCP!

Your Telegram notifications will work perfectly from GCP Cloud Run and Compute Engine. The system uses the standard Telegram Bot API which is accessible from anywhere.

## 📋 Setup Instructions

### 1. Create Your Telegram Bot (If Not Done Already)

1. **Open Telegram** and search for `@BotFather`
2. **Send** `/newbot` and follow instructions
3. **Copy** your bot token (looks like: `123456789:ABCdefGHIjklMNOpqrsTUVwxyz`)

### 2. Get Your Chat ID

1. **Send a message** to your bot
2. **Visit**: `https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getUpdates`
3. **Find** the `"chat":{"id":123456789}` value
4. **Copy** your chat ID

### 3. Configure Secrets

#### Option A: Using config/.env File

Create `config/.env` with:

```bash
TELEGRAM_BOT_TOKEN=123456789:ABCdefGHIjklMNOpqrsTUVwxyz
TELEGRAM_CHAT_ID=123456789
```

Then deploy - the script will automatically store these in Secret Manager.

#### Option B: Manual Secret Creation

```bash
# Create a temporary file with just the token
echo "TELEGRAM_BOT_TOKEN=your_token_here" > telegram-temp.env
echo "TELEGRAM_CHAT_ID=your_chat_id_here" >> telegram-temp.env

# Store in Secret Manager
gcloud secrets create telegram-config --data-file=telegram-temp.env

# Clean up
rm telegram-temp.env
```

### 4. Verify Deployment

The `deploy-gcp.sh` script automatically:
- ✅ Stores secrets in Secret Manager
- ✅ Mounts secrets as environment variables in Cloud Run
- ✅ Makes them available to your Python code

## 🔍 How It Works

### Code Flow

```python
# core/telegram.py
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")  # ← Loaded from Secret Manager
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")      # ← Loaded from Secret Manager

def send_telegram(msg):
    # Sends via Telegram Bot API
    # Works from anywhere with internet access
```

### GCP Secret Manager → Environment Variables

```
Secret Manager (telegram-config)
    ↓
Cloud Run Environment Variables
    ↓
TELEGRAM_BOT_TOKEN=...
TELEGRAM_CHAT_ID=...
    ↓
Python os.getenv()
    ↓
send_telegram() function
```

## 📨 Notifications You'll Receive

### From Analysis Job (4:00 PM)

```
📊 Analysis Complete
Found 5 BUY signals:
• RELIANCE - Strong Buy
• TCS - Buy  
• INFY - Buy
...
```

### From Buy Orders (After Analysis)

```
🛒 AMO Orders Placed
✓ RELIANCE: 10 shares @ ₹2450
✓ TCS: 5 shares @ ₹3850
Total: 2 orders placed
```

### From Sell Engine (During Market Hours)

```
💰 Sell Order Executed
INFY: 15 shares @ ₹1520
P&L: +₹450 (+3.05%)
```

```
⚠️ Insufficient Balance
Symbol: TCS
Required: ₹19,250
Available: ₹15,000
Shortfall: ₹4,250
```

## 🧪 Testing

### Test from Local Machine

```bash
# Set environment variables
export TELEGRAM_BOT_TOKEN="your_token"
export TELEGRAM_CHAT_ID="your_chat_id"

# Run Python test
python3 -c "
from core.telegram import send_telegram
send_telegram('🚀 Test from local machine!')
"
```

### Test from GCP

```bash
# Trigger analysis job manually
gcloud scheduler jobs run trading-workflow-job --location=asia-south1

# Check if notification was sent
# You should receive Telegram messages
```

### Test Specific Notification

```python
# Create a test script
cat > test_telegram.py << 'EOF'
from core.telegram import send_telegram

# Test message
send_telegram("🧪 Test from GCP Cloud Run\n\nIf you receive this, Telegram is working! ✅")
EOF

# Run in Docker (simulates GCP environment)
docker build -t test-telegram .
docker run --rm \
  -e TELEGRAM_BOT_TOKEN="your_token" \
  -e TELEGRAM_CHAT_ID="your_chat_id" \
  test-telegram python test_telegram.py
```

## 🚨 Troubleshooting

### Issue: Not receiving notifications

**Check 1: Secrets are stored**
```bash
gcloud secrets describe telegram-config
gcloud secrets versions access latest --secret=telegram-config
```

**Check 2: Env vars in Cloud Run**
```bash
gcloud run services describe trading-analysis --region=asia-south1 --format=yaml | grep -A5 secrets
```

**Check 3: Test bot manually**
```bash
curl "https://api.telegram.org/bot<YOUR_TOKEN>/sendMessage?chat_id=<YOUR_CHAT_ID>&text=Test"
```

**Check 4: View logs**
```bash
# Check for telegram errors
gcloud logging read 'resource.type="cloud_run_revision" AND "telegram"' --limit=50
```

### Issue: "Telegram token or chat ID not configured"

This warning appears when:
1. Secret not mounted correctly
2. Environment variables not set
3. Secret Manager permissions missing

**Solution:**
```bash
# Verify secret exists
gcloud secrets list | grep telegram

# Grant access to Cloud Run service account
PROJECT_NUMBER=$(gcloud projects describe $PROJECT_ID --format="value(projectNumber)")
gcloud secrets add-iam-policy-binding telegram-config \
    --member="serviceAccount:${PROJECT_NUMBER}-compute@developer.gserviceaccount.com" \
    --role="roles/secretmanager.secretAccessor"

# Redeploy service
./deploy-gcp.sh
```

### Issue: API error 401 (Unauthorized)

Your bot token is invalid or expired.

**Solution:**
1. Verify token with BotFather
2. Update secret: `gcloud secrets versions add telegram-config --data-file=config/.env`
3. Redeploy services

### Issue: Messages sent but not received

**Check:**
1. Did you start a conversation with your bot first?
2. Is the chat ID correct?
3. Was the bot blocked?

**Fix:**
- Send `/start` to your bot
- Verify chat ID from getUpdates API
- Unblock bot if needed

## 🔐 Security

✅ **Secure Storage**: Credentials stored in Secret Manager (encrypted at rest)  
✅ **Least Privilege**: Only required services have access  
✅ **No Hardcoding**: Never in code or logs  
✅ **Audit Trail**: All secret access logged  

## 📊 Monitoring

### Check Notification Success Rate

```bash
# Count successful notifications
gcloud logging read 'resource.type="cloud_run_revision" AND "Telegram message sent successfully"' \
  --limit=100 --format=json | jq 'length'

# Count failed notifications  
gcloud logging read 'resource.type="cloud_run_revision" AND "Telegram send failed"' \
  --limit=100 --format=json | jq 'length'
```

### Alert on Failed Notifications

```yaml
# alert-policy.yaml
displayName: "Telegram Notification Failures"
conditions:
  - displayName: "Too many failed Telegram sends"
    conditionThreshold:
      filter: 'resource.type="cloud_run_revision" AND textPayload=~"Telegram send failed"'
      comparison: COMPARISON_GT
      thresholdValue: 5
      duration: 300s
```

## 💡 Tips

1. **Test First**: Always test with a manual trigger before relying on scheduled jobs
2. **Keep Token Secret**: Never commit to Git
3. **Monitor Logs**: Check for "Telegram message sent successfully" 
4. **Rate Limits**: Telegram allows ~30 messages/second per bot
5. **Message Length**: Max 4096 characters (auto-split in code)

## ✨ Advanced: Rich Formatting

Your notifications support Markdown:

```python
from core.telegram import send_telegram

msg = """
*Trading Alert* 🔔

📈 _Strong Buy Signal_

• Symbol: `RELIANCE`
• Price: ₹2,450
• Score: 85/100

[View Chart](https://example.com)
"""

send_telegram(msg)
```

## 📚 Related

- **GCP Deployment**: [GCP_DEPLOYMENT.md](GCP_DEPLOYMENT.md)
- **Quick Start**: [DEPLOYMENT_QUICKSTART.md](DEPLOYMENT_QUICKSTART.md)
- **Telegram Module**: [core/telegram.py](core/telegram.py)
