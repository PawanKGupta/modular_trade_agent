# Docker Deployment Troubleshooting

## Permission Denied Error

If you see `PermissionError: [Errno 13] Permission denied` when running docker-compose:

### Solution: Add User to Docker Group

```bash
# Add user to docker group
sudo usermod -aG docker $USER

# Apply group changes (logout/login or use newgrp)
newgrp docker

# Verify membership
groups | grep docker

# Test access
docker ps
```

### Alternative: Use sudo (not recommended for production)

```bash
sudo docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

## Common Issues

### Docker Group Doesn't Exist

If docker group doesn't exist:

```bash
sudo groupadd docker
sudo usermod -aG docker $USER
newgrp docker
```

### Docker Daemon Not Running

Check if Docker daemon is running:

```bash
sudo systemctl status docker
```

Start Docker daemon if needed:

```bash
sudo systemctl start docker
sudo systemctl enable docker  # Enable auto-start on boot
```
