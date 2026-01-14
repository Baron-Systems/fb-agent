# Frappe Manager Backup Agent (fb-agent)

**Zero-config backup agent for Frappe Manager production servers.**

## Features

- 🎯 **Zero-Config:** Auto-discovers `fm`, sites, and dashboard
- 🔐 **Secure:** HMAC signatures, allowlisted actions only
- 🔄 **Auto-Register:** Announces to dashboard every 5 minutes
- 🛡️ **Safe:** All operations via `fm shell` - no direct docker/bench access
- 📡 **Lightweight:** Minimal resource usage
- 🔍 **Discovery:** Parses `fm list` to discover sites automatically

## Quick Start

```bash
# Install
pipx install git+https://github.com/Baron-Systems/fb-agent.git

# Run (starts on port 8888)
fb-agent run
```

Agent will automatically:
1. Find `fm` binary in PATH
2. Generate stable agent ID
3. Discover dashboard via UDP broadcast
4. Register with dashboard
5. Start API server
6. Re-announce every 5 minutes

## Requirements

- Python 3.11+
- `fm` (Frappe Manager) in PATH
- Dashboard (`fb`) running on same network

## Supported Actions

Agent only accepts these allowlisted actions:

- `list_sites` - Discover sites via `fm list`
- `backup_site` - Execute backup via `fm shell` + `bench backup`
- `download_artifact` - Download backup files
- `health` - Health check

## Backup Execution

```
User clicks "Backup" in Dashboard UI
         ↓
Dashboard → Agent (POST /api/backup_site)
         ↓
Agent validates site name
         ↓
Execute via PTY:
  fm shell <site>
  bench --site <site> backup
  exit
         ↓
Agent returns backup artifacts
         ↓
Dashboard pulls files to storage
```

## systemd Service

```bash
# Install as service
sudo curl -o /etc/systemd/system/fb-agent.service \
  https://raw.githubusercontent.com/Baron-Systems/fb-agent/main/fb-agent.service

sudo systemctl enable --now fb-agent
```

## Data Locations

- **State:** `~/.local/share/fb-agent/`
- **Shared Secret:** `~/.local/share/fb-agent/shared_secret.txt`

## Security

- ✅ HMAC request signing with timestamp
- ✅ Allowlisted actions only
- ✅ Input validation (site names, paths)
- ✅ No arbitrary command execution
- ✅ Operations only via `fm shell`
- ✅ Backup files restricted to `private/backups` paths

## Troubleshooting

### Agent can't find fm

```bash
# Check fm is in PATH
which fm

# Or create symlink
sudo ln -s /path/to/fm /usr/local/bin/fm
```

### Agent not connecting to Dashboard

1. Check Dashboard is running: `curl http://dashboard_ip:7311/`
2. Check firewall allows port 8888
3. Check logs: `journalctl -u fb-agent -n 50`

## Development

```bash
# Clone
git clone https://github.com/Baron-Systems/fb-agent.git
cd fb-agent

# Install in dev mode
pip install -e .

# Run
python -m fb_agent.cli
```

## License

Proprietary

## Support

Issues: https://github.com/Baron-Systems/fb-agent/issues
