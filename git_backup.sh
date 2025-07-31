# ------------------------------
# git_backup.sh (Place in /mnt/ai-lab/friday/git_backup.sh)
# ------------------------------
#!/bin/bash

set -e

# === CONFIG ===
REPO_DIR="/mnt/ai-lab/friday"
BACKUP_DIR="/media/auston/b6612c61-e508-44f3-a783-f82da142d8d51"
MAX_BACKUPS=3  # Keep the 3 most recent
BRANCH="main"  # Change if your main branch has a different name

cd "$REPO_DIR"

echo "[Git] Staging changes..."
git add .

echo "[Git] Committing..."
COMMIT_MSG="Automated backup commit $(date '+%Y-%m-%d %H:%M:%S')"
git commit -m "$COMMIT_MSG" || echo "[Git] No changes to commit."

echo "[Git] Pushing..."
git push origin "$BRANCH"

# === BACKUP ===
STAMP=$(date +%Y%m%d-%H%M%S)
BACKUP_FILE="$BACKUP_DIR/friday-backup-$STAMP.tar.gz"

echo "[Backup] Creating backup at $BACKUP_FILE..."
tar -czf "$BACKUP_FILE" -C "$REPO_DIR" .

echo "[Backup] Cleaning up old backups (keep $MAX_BACKUPS)..."
cd "$BACKUP_DIR"
ls -tp friday-backup-*.tar.gz | grep -v '/$' | tail -n +$((MAX_BACKUPS + 1)) | xargs -r rm --

echo "[Done] Backup and Git sync complete."

# ------------------------------
# Add to crontab (run `crontab -e`)
# ------------------------------
# Daily Git commit at 6pm
0 18 * * * bash /mnt/ai-lab/friday/git_backup.sh >> /mnt/ai-lab/friday/logs/git_cron.log 2>&1

# Weekly full backup on Sunday at 7pm
0 19 * * 0 bash /mnt/ai-lab/friday/git_backup.sh >> /mnt/ai-lab/friday/logs/backup_cron.log 2>&1

