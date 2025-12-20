# Individual Service Management User Guide

**Version**: 1.0
**Last Updated**: 2025-11-18
**Status**: ✅ Complete

---

## Overview

The Individual Service Management feature allows users to run specific trading tasks independently from the unified service. This provides flexibility to test individual components, run tasks on-demand, and manage services granularly.

---

## Key Concepts

### Unified Service vs Individual Services

- **Unified Service**: Runs all trading tasks automatically on a schedule. When running, individual services cannot be started (to prevent conflicts).
- **Individual Services**: Run specific tasks (e.g., premarket_retry, sell_monitor) independently. Can run on their own schedule or be triggered manually.

### Service States

- **Running**: Service is actively executing tasks
- **Stopped**: Service is not running
- **Disabled**: Schedule is disabled by admin (service cannot run)

---

## User Features

### Accessing Individual Services

1. Navigate to **Service Status** (`/dashboard/service`)
2. Scroll to the **Individual Service Management** section
3. You'll see cards for each available service:
   - Pre-market Retry
   - Sell Monitor
   - Analysis
   - Buy Orders
   - End-of-Day Cleanup

### Starting an Individual Service

**Prerequisites**: Unified service must be stopped.

1. Click **Start Service** on the desired service card
2. The service will start running on its own schedule
3. Status indicator changes to "Running"
4. You'll see the process ID and last execution time

**Note**: If unified service is running, the "Start Service" button is disabled with a tooltip explaining why.

### Stopping an Individual Service

1. Click **Stop Service** on the running service card
2. The service will gracefully shut down
3. Status indicator changes to "Stopped"

### Running a Task Once

**"Run Once"** allows you to execute a task immediately without starting a continuous service:

1. Click **Run Once** on any service card
2. The task executes immediately in a separate thread
3. You'll see a conflict warning if the task is already running in unified service
4. Execution history is logged and visible in the Task Execution History table

**Benefits**:
- Test a specific task without starting the full service
- Run tasks on-demand even when unified service is running
- Quick execution without waiting for scheduled time

### Viewing Service Status

Each service card shows:
- **Status**: Running/Stopped indicator
- **Last Execution**: Time since last execution
- **Next Execution**: When the next scheduled execution will occur
- **Schedule Status**: Enabled/Disabled indicator

---

## Admin Features

### Accessing Schedule Management

1. Navigate to **Admin • Schedules** (`/dashboard/admin/schedules`)
2. You'll see a table of all service schedules

### Viewing Schedules

The schedule table shows:
- **Task Name**: Name of the service
- **Schedule Time**: When the task runs (HH:MM format)
- **Type**: One-time, Hourly, or Continuous
- **Status**: Enabled or Disabled
- **Next Execution**: Calculated next execution time
- **Description**: What the task does

### Editing a Schedule

1. Click **Edit** on the desired schedule row
2. Modify the fields:
   - **Schedule Time**: Change the execution time (HH:MM format)
   - **Hourly**: Check if task runs hourly (deprecated - no hourly tasks currently)
   - **Continuous**: Check if task runs continuously (e.g., sell_monitor)
   - **End Time**: Set end time for continuous tasks
   - **Enabled**: Enable or disable the schedule
   - **Description**: Update the task description
3. Click **Save**
4. A banner will appear indicating that unified service restart is required

### Enabling/Disabling Schedules

**Quick Toggle**:
1. Click **Enable** or **Disable** button on any schedule row
2. The schedule status updates immediately
3. A restart banner appears if needed

**Note**: Disabled schedules won't run in unified service or as individual services.

### Schedule Types

- **One-time**: Runs once per day at the specified time (e.g., premarket_retry at 9:00 AM)
- **Continuous**: Runs continuously from start time to end time (e.g., sell_monitor from 9:15 AM to 3:30 PM)

---

## Conflict Detection

The system automatically detects and prevents conflicts:

### When Unified Service is Running

- **Individual Service Start**: Disabled (prevents duplicate execution)
- **Run Once**: Allowed (runs in addition to scheduled execution)
  - Shows warning if task is currently executing
  - Prevents duplicate if task started within last 2 minutes

### When Unified Service is Stopped

- **Individual Service Start**: Enabled
- **Run Once**: Enabled

### Conflict Warnings

When "Run Once" detects a conflict:
- Yellow warning banner appears
- Message explains the conflict
- Banner auto-dismisses after 5 seconds
- Execution still proceeds (warning only)

---

## Best Practices

### For Regular Users

1. **Use Unified Service** for normal operations (runs all tasks automatically)
2. **Use Individual Services** for:
   - Testing specific tasks
   - Running tasks outside normal schedule
   - Troubleshooting specific components
3. **Use "Run Once"** for:
   - Quick tests
   - On-demand execution
   - Testing without starting full service

### For Admins

1. **Schedule Changes**: Always restart unified service after schedule changes
2. **Testing Schedules**: Use "Run Once" to test schedule changes before enabling
3. **Disable Unused Tasks**: Disable schedules for tasks you don't need
4. **Monitor Conflicts**: Watch for conflict warnings in logs

---

## Troubleshooting

### "Cannot start individual service when unified service is running"

**Solution**: Stop the unified service first, then start the individual service.

### "Service is already running"

**Solution**: The service is already running. Check the status indicator. If you need to restart, stop it first, then start again.

### "Schedule changes require restart"

**Solution**: Stop and restart the unified service to apply schedule changes.

### Service Not Running After Start

**Check**:
1. Is the schedule enabled? (Look for "Disabled" badge)
2. Is unified service running? (Individual services can't start if unified is running)
3. Check service logs for errors
4. Verify user has proper permissions

---

## API Reference

### Individual Service Endpoints

- `GET /api/v1/user/service/individual/status` - Get status of all individual services
- `POST /api/v1/user/service/individual/start` - Start an individual service
- `POST /api/v1/user/service/individual/stop` - Stop an individual service
- `POST /api/v1/user/service/individual/run-once` - Run a task once

### Admin Schedule Endpoints

- `GET /api/v1/admin/schedules` - List all schedules
- `GET /api/v1/admin/schedules/{task_name}` - Get specific schedule
- `PUT /api/v1/admin/schedules/{task_name}` - Update schedule
- `POST /api/v1/admin/schedules/{task_name}/enable` - Enable schedule
- `POST /api/v1/admin/schedules/{task_name}/disable` - Disable schedule

---

## Related Documentation

- [Service Status & Trading Config UI Guide](./SERVICE_STATUS_AND_TRADING_CONFIG_UI.md)
- [Individual Service Management Implementation Plan](./INDIVIDUAL_SERVICE_MANAGEMENT_IMPLEMENTATION_PLAN.md)
