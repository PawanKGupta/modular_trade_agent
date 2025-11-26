# Shared Scheduler Refactoring Proposal

## 🎯 **Goal**
Extract duplicate scheduler logic into a shared `UnifiedTaskScheduler` component that can be used by both paper trading and real trading services.

---

## 📊 **Current State**

### **Duplicated Code:**
- `src/application/services/multi_user_trading_service.py::_run_paper_trading_scheduler()` (~200 lines)
- `modules/kotak_neo_auto_trader/run_trading_service.py::run()` (~200 lines)

### **Common Logic:**
Both schedulers do the same thing:
1. Check if it's a trading day
2. Get current time
3. Read task schedules from database
4. Check if it's time to run each task
5. Execute task methods
6. Update heartbeat
7. Handle errors
8. Sleep and repeat

### **Only Difference:**
- **Task execution**: Different methods are called (`service.run_analysis()` vs `self.run_analysis()`)
- **Error handling**: Slightly different logging

---

## ✅ **Proposed Solution**

### **1. Create TaskExecutor Interface**

```python
# src/application/services/task_executor_interface.py

from abc import ABC, abstractmethod
from typing import Dict

class TaskExecutor(ABC):
    """Interface for task execution (paper trading or real trading)"""
    
    @abstractmethod
    def run_premarket_retry(self) -> None:
        """Execute pre-market retry task"""
        pass
    
    @abstractmethod
    def run_sell_monitor(self) -> None:
        """Execute sell monitoring task"""
        pass
    
    @abstractmethod
    def run_position_monitor(self) -> None:
        """Execute position monitoring task"""
        pass
    
    @abstractmethod
    def run_buy_orders(self) -> None:
        """Execute buy orders task"""
        pass
    
    @abstractmethod
    def run_eod_cleanup(self) -> None:
        """Execute end-of-day cleanup task"""
        pass
    
    @abstractmethod
    def adjust_amo_quantities_premarket(self) -> None:
        """Execute pre-market AMO adjustment task"""
        pass
    
    @property
    @abstractmethod
    def tasks_completed(self) -> Dict[str, bool]:
        """Get tasks completion tracking dict"""
        pass
    
    @property
    @abstractmethod
    def running(self) -> bool:
        """Check if executor is running"""
        pass
    
    @running.setter
    @abstractmethod
    def running(self, value: bool):
        """Set executor running state"""
        pass
```

---

### **2. Create Unified Scheduler**

```python
# src/application/services/unified_task_scheduler.py

from datetime import datetime, time as dt_time
import time
from typing import Optional

from src.application.services.schedule_manager import ScheduleManager
from src.application.services.task_executor_interface import TaskExecutor
from src.infrastructure.logging import get_user_logger

class UnifiedTaskScheduler:
    """
    Unified task scheduler that works with any TaskExecutor.
    Reads schedules from database and executes tasks at scheduled times.
    """
    
    def __init__(
        self, 
        user_id: int, 
        db_session, 
        task_executor: TaskExecutor,
        logger_module: str = "TaskScheduler"
    ):
        self.user_id = user_id
        self.db = db_session
        self.executor = task_executor
        self.schedule_manager = ScheduleManager(db_session)
        self.logger = get_user_logger(user_id=user_id, db=db_session, module=logger_module)
        self.last_check: Optional[str] = None
        self.heartbeat_counter = 0
    
    def run_scheduler_loop(self):
        """Main scheduler loop - runs continuously"""
        self.logger.info("Scheduler started")
        self.executor.running = True
        
        while self.executor.running:
            try:
                now = datetime.now()
                current_time = now.time()
                
                # Check only once per minute
                current_minute = now.strftime("%Y-%m-%d %H:%M")
                if current_minute == self.last_check:
                    time.sleep(1)
                    continue
                
                self.last_check = current_minute
                
                # Only run on trading days (Monday-Friday)
                if now.weekday() >= 5:
                    time.sleep(60)
                    continue
                
                # Execute scheduled tasks
                self._check_and_run_tasks(now, current_time)
                
                # Update heartbeat
                self._update_heartbeat()
                
                time.sleep(1)
                
            except Exception as e:
                self.logger.error(f"Scheduler error: {e}", exc_info=True)
                time.sleep(60)
        
        self.logger.info("Scheduler stopped")
    
    def _check_and_run_tasks(self, now: datetime, current_time: dt_time):
        """Check all tasks and run if scheduled"""
        
        # Pre-market retry
        premarket_schedule = self.schedule_manager.get_schedule("premarket_retry")
        if premarket_schedule and premarket_schedule.enabled:
            premarket_time = premarket_schedule.schedule_time
            if self._is_time_to_run(current_time, premarket_time):
                if not self.executor.tasks_completed.get("premarket_retry"):
                    self._run_task("premarket_retry", self.executor.run_premarket_retry)
        
        # Pre-market AMO adjustment (5 mins after premarket retry)
        if self._is_time_to_run(current_time, dt_time(9, 5)):
            if not self.executor.tasks_completed.get("premarket_amo_adjustment"):
                self._run_task("premarket_amo_adjustment", 
                              self.executor.adjust_amo_quantities_premarket)
        
        # Sell monitoring (continuous)
        sell_schedule = self.schedule_manager.get_schedule("sell_monitor")
        if sell_schedule and sell_schedule.enabled and sell_schedule.is_continuous:
            start_time = sell_schedule.schedule_time
            end_time = sell_schedule.end_time or dt_time(15, 30)
            if self._is_in_time_range(current_time, start_time, end_time):
                self._run_task("sell_monitor", self.executor.run_sell_monitor)
        
        # Position monitoring (hourly)
        position_schedule = self.schedule_manager.get_schedule("position_monitor")
        if position_schedule and position_schedule.enabled and position_schedule.is_hourly:
            start_time = position_schedule.schedule_time
            if current_time.minute == start_time.minute and start_time.hour <= now.hour <= 15:
                hour_key = now.strftime("%Y-%m-%d %H")
                if not self.executor.tasks_completed.get("position_monitor", {}).get(hour_key):
                    self._run_task("position_monitor", self.executor.run_position_monitor)
        
        # Analysis (via Individual Service Manager for paper trading)
        analysis_schedule = self.schedule_manager.get_schedule("analysis")
        if analysis_schedule and analysis_schedule.enabled:
            analysis_time = analysis_schedule.schedule_time
            if self._is_time_to_run(current_time, analysis_time):
                if not self.executor.tasks_completed.get("analysis"):
                    # For paper trading, this triggers Individual Service Manager
                    # For real trading, this calls self.run_analysis()
                    self._trigger_analysis(analysis_time)
        
        # Buy orders
        buy_schedule = self.schedule_manager.get_schedule("buy_orders")
        if buy_schedule and buy_schedule.enabled:
            buy_time = buy_schedule.schedule_time
            if self._is_time_to_run(current_time, buy_time):
                if not self.executor.tasks_completed.get("buy_orders"):
                    self._run_task("buy_orders", self.executor.run_buy_orders)
        
        # EOD cleanup
        eod_schedule = self.schedule_manager.get_schedule("eod_cleanup")
        if eod_schedule and eod_schedule.enabled:
            eod_time = eod_schedule.schedule_time
            if self._is_time_to_run(current_time, eod_time):
                if not self.executor.tasks_completed.get("eod_cleanup"):
                    self._run_task("eod_cleanup", self.executor.run_eod_cleanup)
    
    def _is_time_to_run(self, current_time: dt_time, scheduled_time: dt_time) -> bool:
        """Check if current time matches scheduled time (within 1 minute)"""
        return (dt_time(scheduled_time.hour, scheduled_time.minute) 
                <= current_time 
                < dt_time(scheduled_time.hour, scheduled_time.minute + 1))
    
    def _is_in_time_range(self, current_time: dt_time, start: dt_time, end: dt_time) -> bool:
        """Check if current time is in range [start, end]"""
        return (current_time >= dt_time(start.hour, start.minute) 
                and current_time <= dt_time(end.hour, end.minute))
    
    def _run_task(self, task_name: str, task_func):
        """Execute a task with error handling"""
        try:
            task_func()
        except Exception as e:
            self.logger.error(f"{task_name} failed: {e}", exc_info=True, action="scheduler")
    
    def _trigger_analysis(self, analysis_time: dt_time):
        """Special handling for analysis task (may need Individual Service Manager)"""
        # Implementation depends on whether it's paper trading or real trading
        # This would be customized per executor type
        pass
    
    def _update_heartbeat(self):
        """Update heartbeat in database"""
        from src.infrastructure.persistence.service_status_repository import ServiceStatusRepository
        
        try:
            status_repo = ServiceStatusRepository(self.db)
            status_repo.update_heartbeat(self.user_id)
            self.db.commit()
            
            # Log heartbeat periodically
            self.heartbeat_counter += 1
            if self.heartbeat_counter == 1 or self.heartbeat_counter % 300 == 0:
                self.logger.info(
                    f"💓 Scheduler heartbeat (running for {self.heartbeat_counter // 60} minutes)",
                    action="scheduler"
                )
        except Exception as e:
            self.logger.warning(f"Failed to update heartbeat: {e}", action="scheduler")
            self.db.rollback()
```

---

### **3. Update PaperTradingServiceAdapter**

```python
# src/application/services/paper_trading_service_adapter.py

from src.application.services.task_executor_interface import TaskExecutor

class PaperTradingServiceAdapter(TaskExecutor):
    """Implements TaskExecutor interface for paper trading"""
    
    # Existing code...
    
    # Already implements all required methods:
    # - run_premarket_retry()
    # - run_sell_monitor()
    # - run_position_monitor()
    # - run_buy_orders()
    # - run_eod_cleanup()
    # - adjust_amo_quantities_premarket()
    # - tasks_completed property
    # - running property
```

---

### **4. Update TradingService**

```python
# modules/kotak_neo_auto_trader/run_trading_service.py

from src.application.services.task_executor_interface import TaskExecutor

class TradingService(TaskExecutor):
    """Implements TaskExecutor interface for real trading"""
    
    # Existing code...
    
    # Already implements all required methods
```

---

### **5. Update MultiUserTradingService**

```python
# src/application/services/multi_user_trading_service.py

def _run_paper_trading_scheduler(self, service: PaperTradingServiceAdapter, user_id: int):
    """Run paper trading service scheduler (now uses shared scheduler)"""
    from src.infrastructure.db.session import SessionLocal
    from src.application.services.unified_task_scheduler import UnifiedTaskScheduler
    
    thread_db = SessionLocal()
    
    try:
        scheduler = UnifiedTaskScheduler(
            user_id=user_id,
            db_session=thread_db,
            task_executor=service,
            logger_module="PaperTradingScheduler"
        )
        scheduler.run_scheduler_loop()
    finally:
        thread_db.close()
```

---

## 📊 **Benefits**

| Benefit | Impact |
|---------|--------|
| **No Code Duplication** | ~200 lines → Single source of truth |
| **Easier Maintenance** | Fix once, works everywhere |
| **Consistent Behavior** | Same logic for all brokers |
| **Better Testing** | Test scheduler once |
| **Extensible** | Easy to add new broker types |

---

## ⚠️ **Risks**

1. **Refactoring Effort**: ~4-6 hours of work
2. **Testing Required**: Must test both paper and real trading
3. **Potential Regressions**: Changes to core scheduler logic
4. **Migration Path**: Need to ensure backward compatibility

---

## 🎯 **Recommendation**

**Status**: **Nice-to-have refactoring** (not urgent)

**Priority**: Low-Medium (technical debt)

**Timing**: 
- ✅ **Now**: The current fix works for both
- 🔄 **Later**: Refactor when adding new broker types or major scheduler changes

---

## 📝 **Implementation Plan**

1. Create `TaskExecutor` interface
2. Create `UnifiedTaskScheduler` class
3. Make `PaperTradingServiceAdapter` implement interface (no changes needed)
4. Make `TradingService` implement interface (no changes needed)
5. Update `MultiUserTradingService` to use unified scheduler
6. Add comprehensive tests
7. Migrate gradually (feature flag?)
8. Remove old scheduler code

**Estimated Effort**: 1-2 days

---

**Current Status**: We've fixed the immediate bugs. This refactoring is optional but would improve code quality long-term.

