# Health Check Documentation

## Overview
The health check utility verifies the complete installation and configuration of the Modular Trade Agent, ensuring all components are properly set up and functioning.

## Running the Health Check

### Method 1: Using the Batch File (Easiest)
Double-click `scripts\\health_check.bat` or run from command prompt:
```cmd
scripts\health_check.bat
```

### Method 2: Direct Python Execution
```cmd
python health_check.py
```

### Method 3: From Installed Location
If the agent is installed via the installer:
```cmd
C:\ProgramData\ModularTradeAgent\python\python.exe health_check.py
```

## What Gets Checked

### 1. Installation Verification
- Installation directory existence
- Required files presence
- Python executable availability
- NSSM service manager

### 2. Configuration Files
- `.env` file existence and validity
- Required environment variables
- Credentials configuration
- API keys and tokens

### 3. Service Status
- Windows service installation
- Service current state (running/stopped)
- Service configuration

### 4. Scripts and Executables
- Batch scripts availability
- Start/Stop/Launch scripts
- Service control scripts

### 5. Dependencies
- Python package installations
- Required libraries verification
- Version compatibility

### 6. Data Directory
- Data folder structure
- Model files
- Cache directories
- Write permissions

### 7. Logs
- Log directory access
- Recent log files
- Error patterns in logs

## Output Interpretation

### Status Indicators
- ✓ **PASS**: Component is working correctly
- ✗ **FAIL**: Critical issue that needs immediate attention
- ⚠ **WARNING**: Non-critical issue or recommendation

### Summary Section
At the end of the check, you'll see:
```
==========================================
Health Check Summary
==========================================
Total Checks: XX
Passed: XX
Failed: XX
Warnings: XX
==========================================
```

### Exit Codes
- `0`: All checks passed
- `1`: One or more checks failed (requires attention)

## Common Issues and Solutions

### Issue: `.env` file not found
**Solution**: 
- Copy `.env.example` to `.env`
- Configure required credentials
- Run health check again

### Issue: Service not installed
**Solution**:
- Run the installer
- Or manually install: `install_service.bat`

### Issue: Python dependencies missing
**Solution**:
```cmd
pip install -r requirements.txt
```

### Issue: Permission denied on data directory
**Solution**:
- Run as Administrator
- Or grant write permissions to the user running the service

### Issue: Configuration variables missing
**Solution**:
Edit `.env` file and ensure all required variables are set:
- `TRADINGVIEW_USERNAME`
- `TRADINGVIEW_PASSWORD`
- `GROQ_API_KEY`
- `OPENAI_API_KEY` (optional)
- `ANTHROPIC_API_KEY` (optional)

## Automated Health Checks

### Scheduled Task
You can set up a Windows scheduled task to run health checks periodically:

1. Open Task Scheduler
2. Create Basic Task
3. Set trigger (e.g., daily at startup)
4. Action: Start a program
5. Program: `C:\ProgramData\ModularTradeAgent\python\python.exe`
6. Arguments: `health_check.py`
7. Start in: `C:\ProgramData\ModularTradeAgent`

### Script Integration
You can integrate health checks into your monitoring scripts:

```python
import subprocess

result = subprocess.run(['python', 'health_check.py'], capture_output=True)
if result.returncode != 0:
    # Send alert or notification
    send_alert("Health check failed!")
```

## Troubleshooting

### Health Check Won't Run
1. Verify Python is in PATH
2. Check file permissions
3. Run as Administrator if needed
4. Check Python installation

### Incomplete Results
- Ensure all dependencies are installed
- Check log file permissions
- Verify installation directory access

### False Positives
Some warnings may be expected in certain configurations:
- OpenAI/Anthropic keys not required if using only Groq
- Some optional features may show warnings

## Best Practices

1. **Run health check after installation**
   - Verify everything is set up correctly
   - Address any issues before starting the service

2. **Run before troubleshooting**
   - Quickly identify problem areas
   - Get comprehensive status overview

3. **Include in deployment scripts**
   - Automated verification
   - Continuous monitoring

4. **Review warnings**
   - Even if not critical, warnings can indicate future issues
   - Address warnings during maintenance windows

## Support

If health check reveals issues you can't resolve:
1. Review the detailed output
2. Check log files in `logs/` directory
3. Consult the main documentation
4. Check GitHub issues or create a new one with health check output

---

**Note**: The health check is read-only and safe to run anytime without affecting the running service.
