#!/bin/bash
# Deploy x-engagement to Oracle Cloud VM.
# Run from your LOCAL machine: bash deploy.sh ubuntu@<your-vm-ip>
#
# Usage:
#   bash deploy.sh ubuntu@123.456.78.90

set -e

REMOTE=${1:?"Usage: $0 user@host"}
REMOTE_DIR="/home/ubuntu/x-engagement"

echo "==> Syncing files to $REMOTE:$REMOTE_DIR ..."
rsync -avz --exclude='.git' --exclude='__pycache__' --exclude='*.pyc' \
  --exclude='data/' --exclude='logs/' --exclude='venv/' \
  "$(dirname "$0")/" "$REMOTE:$REMOTE_DIR/"

echo "==> Setting up virtualenv and installing dependencies..."
ssh "$REMOTE" bash << 'EOF'
  cd /home/ubuntu/x-engagement
  python3 -m venv venv
  source venv/bin/activate
  pip install --quiet --upgrade pip
  pip install --quiet -r requirements.txt
  mkdir -p logs data
  chmod 700 data
  echo "Dependencies installed."
EOF

echo ""
echo "==> Deploy complete!"
echo ""
echo "Next steps on the VM:"
echo "  1. Copy your credentials:  nano /home/ubuntu/x-engagement/.env"
echo "     (use .env.example as a template, chmod 600 .env afterwards)"
echo ""
echo "  2. Run one-time account setup:"
echo "     cd /home/ubuntu/x-engagement && source venv/bin/activate && python setup.py"
echo ""
echo "  3. Test the full pipeline:"
echo "     python run_daily.py"
echo ""
echo "  4. Add cron job (08:00 UTC daily):"
echo "     crontab -e"
echo "     Add: 0 8 * * * cd /home/ubuntu/x-engagement && /home/ubuntu/x-engagement/venv/bin/python run_daily.py >> logs/engagement.log 2>&1"
