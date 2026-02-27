#!/usr/bin/env python3
"""
Digest Scheduler
定时任务调度器
"""

import time
import threading
from datetime import datetime
from typing import Dict, Callable
from pathlib import Path
import json


# 配置
AGENTSYS_ROOT = Path(__file__).parent.parent.parent
SCHEDULER_STATE = AGENTSYS_ROOT / "数据" / "digest" / "scheduler_state.json"


# 调度配置
SCHEDULE_CONFIG = {
    "4h": {
        "name": "增量摘要",
        "description": "每4小时生成增量摘要",
        "enabled": True
    },
    "daily": {
        "name": "日度摘要",
        "description": "每天早上生成日度摘要",
        "enabled": True
    },
    "weekly": {
        "name": "周度摘要",
        "description": "每周一生成周度摘要",
        "enabled": True
    },
    "monthly": {
        "name": "月度摘要",
        "description": "每月1号生成月度摘要",
        "enabled": True
    }
}


class DigestScheduler:
    """摘要调度器"""

    def __init__(self):
        self.running = False
        self.jobs = {}
        self.last_run = self._load_state()

    def _load_state(self) -> Dict:
        """加载调度状态"""
        if SCHEDULER_STATE.exists():
            try:
                return json.loads(SCHEDULER_STATE.read_text())
            except:
                pass
        return {}

    def _save_state(self):
        """保存调度状态"""
        SCHEDULER_STATE.parent.mkdir(parents=True, exist_ok=True)
        SCHEDULER_STATE.write_text(json.dumps(self.last_run, indent=2))

    def register_job(self, job_id: str, func: Callable, schedule: str = "daily"):
        """
        注册定时任务

        Args:
            job_id: 任务 ID
            func: 任务函数
            schedule: 调度类型 (4h, daily, weekly, monthly)
        """
        self.jobs[job_id] = {
            "func": func,
            "schedule": schedule,
            "last_run": self.last_run.get(job_id)
        }

    def should_run(self, job_id: str, schedule: str) -> bool:
        """检查任务是否应该运行"""
        from datetime import datetime, timedelta

        now = datetime.now()
        last = self.last_run.get(job_id)

        if not last:
            return True

        last_time = datetime.fromisoformat(last)

        # 根据调度类型判断
        if schedule == "4h":
            # 每4小时
            return (now - last_time).total_seconds() >= 4 * 3600
        elif schedule == "daily":
            # 每天早上8点
            return now.hour >= 8 and (now - last_time).total_seconds() >= 20 * 3600
        elif schedule == "weekly":
            # 每周一
            return now.weekday() == 0 and now.hour >= 8
        elif schedule == "monthly":
            # 每月1号
            return now.day == 1 and now.hour >= 8

        return False

    def run_job(self, job_id: str):
        """运行任务"""
        job = self.jobs.get(job_id)
        if not job:
            return

        print(f"[Scheduler] 运行任务: {job_id}")
        try:
            job["func"]()
            self.last_run[job_id] = datetime.now().isoformat()
            self._save_state()
            print(f"[Scheduler] 任务完成: {job_id}")
        except Exception as e:
            print(f"[Scheduler] 任务失败: {job_id} - {e}")

    def start(self):
        """启动调度器"""
        self.running = True
        print("[Scheduler] 调度器已启动")

        while self.running:
            for job_id, job in self.jobs.items():
                if self.should_run(job_id, job["schedule"]):
                    self.run_job(job_id)

            # 每分钟检查一次
            time.sleep(60)

    def stop(self):
        """停止调度器"""
        self.running = False
        print("[Scheduler] 调度器已停止")

    def status(self) -> Dict:
        """获取调度状态"""
        return {
            "running": self.running,
            "jobs": {
                job_id: {
                    "schedule": job["schedule"],
                    "last_run": job.get("last_run")
                }
                for job_id, job in self.jobs.items()
            },
            "config": SCHEDULE_CONFIG
        }


# 全局调度器实例
_scheduler = None


def get_scheduler() -> DigestScheduler:
    """获取调度器实例"""
    global _scheduler
    if _scheduler is None:
        _scheduler = DigestScheduler()
    return _scheduler


import sys
from pathlib import Path
AGENTSYS_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(AGENTSYS_ROOT / "scripts"))


def run_digest_job(digest_type: str = "daily"):
    """运行摘要生成任务"""
    from digest import generator
    print(f"[Job] 生成 {digest_type} 摘要...")
    generator.generate_digest(digest_type=digest_type)
    print(f"[Job] {digest_type} 摘要生成完成")


def start_scheduler():
    """启动调度器（后台运行）"""
    scheduler = get_scheduler()

    # 注册任务
    scheduler.register_job("digest_4h", lambda: run_digest_job("4h"), "4h")
    scheduler.register_job("digest_daily", lambda: run_digest_job("daily"), "daily")
    scheduler.register_job("digest_weekly", lambda: run_digest_job("weekly"), "weekly")
    scheduler.register_job("digest_monthly", lambda: run_digest_job("monthly"), "monthly")

    # 后台线程运行
    thread = threading.Thread(target=scheduler.start, daemon=True)
    thread.start()

    return scheduler


# CLI 接口
if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("用法:")
        print("  python -m digest.scheduler status    - 查看调度状态")
        print("  python -m digest.scheduler run       - 立即运行所有任务")
        print("  python -m digest.scheduler start      - 启动调度器")
        sys.exit(1)

    command = sys.argv[1]

    if command == "status":
        scheduler = get_scheduler()
        status = scheduler.status()
        print(json.dumps(status, indent=2, ensure_ascii=False))

    elif command == "run":
        print("运行所有摘要任务...")
        run_digest_job("4h")
        run_digest_job("daily")

    elif command == "start":
        print("启动调度器...")
        start_scheduler()
        print("调度器已启动，按 Ctrl+C 停止")

        try:
            while True:
                time.sleep(60)
        except KeyboardInterrupt:
            print("\n停止调度器...")

    else:
        print(f"未知命令: {command}")
