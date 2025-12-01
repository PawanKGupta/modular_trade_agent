# Manual Testing Checklist: Notification Preferences

**Feature**: Notification Preferences
**Date**: 2025-11-30
**Tester**: _______________

## Prerequisites

- [ ] Backend server is running
- [ ] Frontend dev server is running
- [ ] Database is accessible
- [ ] User account exists and is logged in
- [ ] Telegram bot is configured (if testing Telegram notifications)

---

## 1. UI Navigation & Access

### 1.1 Navigation
- [ ] Navigate to `/dashboard/notification-preferences`
- [ ] Verify "Notifications" link appears in sidebar navigation
- [ ] Click "Notifications" link - page loads correctly
- [ ] Verify page title shows "Notification Preferences"

### 1.2 Page Loading
- [ ] Page shows "Loading notification preferences..." initially
- [ ] Page loads preferences successfully
- [ ] All sections are visible and properly formatted

---

## 2. Notification Channels

### 2.1 In-App Notifications
- [ ] Toggle "In-App Notifications" on/off
- [ ] Verify checkbox state persists (until save)
- [ ] Verify "Unsaved changes" indicator appears

### 2.2 Telegram
- [ ] Toggle "Telegram" on
- [ ] Verify "Telegram Chat ID" input field appears
- [ ] Enter a chat ID (e.g., "123456789")
- [ ] Toggle "Telegram" off
- [ ] Verify "Telegram Chat ID" input field disappears
- [ ] Toggle back on - verify chat ID is preserved

### 2.3 Email
- [ ] Toggle "Email" on
- [ ] Verify "Email address" input field appears
- [ ] Enter an email address (e.g., "test@example.com")
- [ ] Toggle "Email" off
- [ ] Verify "Email address" input field disappears
- [ ] Toggle back on - verify email is preserved

---

## 3. Order Events

### 3.1 Individual Toggles
- [ ] Toggle each order event on/off:
  - [ ] Order Placed
  - [ ] Order Executed
  - [ ] Order Rejected
  - [ ] Order Cancelled
  - [ ] Order Modified (Manual)
  - [ ] Partial Fill
- [ ] Verify each toggle works independently
- [ ] Verify "Unsaved changes" appears when any toggle changes

### 3.2 Quick Actions
- [ ] Click "Enable All" - verify all order events are enabled
- [ ] Click "Disable All" - verify all order events are disabled
- [ ] Toggle individual events - verify they work independently

---

## 4. Retry Queue Events

### 4.1 Individual Toggles
- [ ] Toggle each retry queue event on/off:
  - [ ] Order Added to Retry Queue
  - [ ] Retry Queue Updated
  - [ ] Order Removed from Retry Queue
  - [ ] Order Retried Successfully
- [ ] Verify each toggle works independently

### 4.2 Quick Actions
- [ ] Click "Enable All" - verify all retry queue events are enabled
- [ ] Click "Disable All" - verify all retry queue events are disabled

---

## 5. System Events

### 5.1 Individual Toggles
- [ ] Toggle each system event on/off:
  - [ ] System Errors
  - [ ] System Warnings
  - [ ] System Info
- [ ] Verify each toggle works independently

### 5.2 Quick Actions
- [ ] Click "Enable All" - verify all system events are enabled
- [ ] Click "Disable All" - verify all system events are disabled

---

## 6. Quiet Hours

### 6.1 Setting Quiet Hours
- [ ] Set start time (e.g., "22:00")
- [ ] Set end time (e.g., "08:00")
- [ ] Verify times are displayed correctly
- [ ] Verify message shows: "Notifications will be suppressed between 22:00 and 08:00"

### 6.2 Clearing Quiet Hours
- [ ] Click "Clear" button
- [ ] Verify start and end time inputs are cleared
- [ ] Verify message disappears

### 6.3 Edge Cases
- [ ] Set quiet hours spanning midnight (e.g., 22:00 - 08:00)
- [ ] Set quiet hours same day (e.g., 14:00 - 16:00)
- [ ] Set only start time (should work)
- [ ] Set only end time (should work)

---

## 7. Save Functionality

### 7.1 Save Button States
- [ ] Verify "Save Preferences" button is disabled when no changes
- [ ] Make a change - verify button becomes enabled
- [ ] Click save - verify button shows "Saving..." during save
- [ ] After save - verify button is disabled again

### 7.2 Save Success
- [ ] Make changes to preferences
- [ ] Click "Save Preferences"
- [ ] Verify success message appears: "Notification preferences saved successfully!"
- [ ] Verify success message auto-dismisses after 3 seconds
- [ ] Verify "Unsaved changes" indicator disappears
- [ ] Refresh page - verify changes are persisted

### 7.3 Save Failure
- [ ] Disconnect network (or stop backend)
- [ ] Make changes and click save
- [ ] Verify error message appears
- [ ] Verify error message shows API error details
- [ ] Verify error message auto-dismisses after 5 seconds

---

## 8. API Integration

### 8.1 Fetch Preferences
- [ ] Open browser DevTools Network tab
- [ ] Navigate to notification preferences page
- [ ] Verify GET request to `/api/v1/user/notification-preferences`
- [ ] Verify request includes Authorization header
- [ ] Verify response contains all preference fields

### 8.2 Update Preferences
- [ ] Make changes and save
- [ ] Verify PUT request to `/api/v1/user/notification-preferences`
- [ ] Verify request body contains only changed fields
- [ ] Verify response contains updated preferences

---

## 9. End-to-End Notification Flow

### 9.1 Order Placed Notification
- [ ] Enable "Order Placed" notification
- [ ] Enable Telegram channel
- [ ] Save preferences
- [ ] Trigger an order placement (via trading service)
- [ ] Verify Telegram notification is received
- [ ] Disable "Order Placed" notification
- [ ] Save preferences
- [ ] Trigger another order placement
- [ ] Verify NO Telegram notification is received

### 9.2 Order Modified Notification
- [ ] Enable "Order Modified (Manual)" notification (opt-in)
- [ ] Save preferences
- [ ] Manually modify an order (via broker interface)
- [ ] Verify Telegram notification is received
- [ ] Disable "Order Modified" notification
- [ ] Save preferences
- [ ] Manually modify another order
- [ ] Verify NO Telegram notification is received

### 9.3 Quiet Hours
- [ ] Set quiet hours (e.g., 22:00 - 08:00)
- [ ] Enable all notifications
- [ ] Save preferences
- [ ] **During quiet hours**: Trigger a notification
- [ ] Verify NO notification is sent
- [ ] **Outside quiet hours**: Trigger a notification
- [ ] Verify notification IS sent

### 9.4 Channel Selection
- [ ] Enable Telegram only
- [ ] Disable Email and In-App
- [ ] Save preferences
- [ ] Trigger a notification
- [ ] Verify notification goes to Telegram only
- [ ] Enable Email only
- [ ] Disable Telegram and In-App
- [ ] Save preferences
- [ ] Trigger a notification
- [ ] Verify notification goes to Email only (if email service is configured)

---

## 10. Multi-User Isolation

### 10.1 User Isolation
- [ ] Login as User 1
- [ ] Set preferences (e.g., enable Telegram)
- [ ] Save preferences
- [ ] Logout
- [ ] Login as User 2
- [ ] Verify User 2 sees default preferences (Telegram disabled)
- [ ] Set different preferences for User 2
- [ ] Save preferences
- [ ] Logout and login as User 1
- [ ] Verify User 1's preferences are unchanged

---

## 11. Error Handling

### 11.1 Network Errors
- [ ] Stop backend server
- [ ] Navigate to notification preferences page
- [ ] Verify error is handled gracefully
- [ ] Restart backend server
- [ ] Refresh page - verify preferences load

### 11.2 Invalid Input
- [ ] Enter invalid email format
- [ ] Verify browser validation (if implemented)
- [ ] Enter very long chat ID
- [ ] Verify input is accepted (validation may be server-side)

---

## 12. Responsive Design

### 12.1 Desktop
- [ ] Verify layout is readable on desktop (1920x1080)
- [ ] Verify all sections are visible without scrolling
- [ ] Verify buttons are easily clickable

### 12.2 Tablet
- [ ] Resize browser to tablet size (768x1024)
- [ ] Verify layout adapts correctly
- [ ] Verify all functionality works

### 12.3 Mobile
- [ ] Resize browser to mobile size (375x667)
- [ ] Verify layout adapts correctly
- [ ] Verify all functionality works
- [ ] Verify form inputs are usable

---

## 13. Accessibility

### 13.1 Keyboard Navigation
- [ ] Tab through all form elements
- [ ] Verify focus indicators are visible
- [ ] Verify all interactive elements are reachable
- [ ] Verify Enter key activates buttons

### 13.2 Screen Reader
- [ ] Use screen reader (if available)
- [ ] Verify all form labels are announced
- [ ] Verify button purposes are clear
- [ ] Verify error messages are announced

---

## 14. Performance

### 14.1 Load Time
- [ ] Measure time to load preferences page
- [ ] Verify page loads in < 2 seconds (on good connection)

### 14.2 Save Time
- [ ] Measure time to save preferences
- [ ] Verify save completes in < 1 second

---

## Test Results Summary

**Total Test Cases**: 100+
**Passed**: _______
**Failed**: _______
**Blocked**: _______

**Critical Issues Found**:
1. _________________________________________________
2. _________________________________________________
3. _________________________________________________

**Minor Issues Found**:
1. _________________________________________________
2. _________________________________________________

**Notes**:
_________________________________________________
_________________________________________________
_________________________________________________

**Tester Signature**: _______________
**Date**: _______________
