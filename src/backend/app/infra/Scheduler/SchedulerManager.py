#!/usr/bin/python
# _*_coding:utf-8_*_
# @author   : mw
# @time     : 2026/04/23
# @function : 定时任务操作
# @version  : v1.0

import asyncio
import inspect
from datetime import datetime, timedelta, timezone
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.job import Job

from app.core.middleware.LogRecorder import get_logger

logger = get_logger(__name__)


class SchedulerManager:
    def __init__(self):
        self.scheduler = AsyncIOScheduler()

    def _wrap_func(self, func):
        async def wrapper():
            try:
                if inspect.iscoroutinefunction(func):
                    await func()
                else:
                    loop = asyncio.get_event_loop()
                    await loop.run_in_executor(None, func)
            except Exception as e:
                logger.exception("定时任务执行失败 task=%s error=%s", func.__name__, e)

        return wrapper

    # =========================
    # 添加任务
    # =========================
    def add_task(
        self,
        task_id: str,
        func,
        interval_seconds: int,
        initial_delay_seconds: float | None = None,
    ):
        """
        添加一个间隔执行的任务（每X秒执行一次）
        :param task_id: 任务唯一 ID
        :param func: 要执行的函数
        :param interval_seconds: 执行间隔（秒）
        :param initial_delay_seconds: 首次执行的延迟（秒），用于错峰采集
        """
        if self.scheduler.get_job(task_id):
            self.scheduler.remove_job(task_id)

        job_options = {
            "max_instances": 1,      # 防止重叠执行
            "coalesce": True,        # 合并错过的任务
            "misfire_grace_time": 30 # 最大延迟容忍
        }
        if initial_delay_seconds is not None:
            job_options["next_run_time"] = datetime.now(timezone.utc) + timedelta(
                seconds=max(0, initial_delay_seconds)
            )

        self.scheduler.add_job(
            self._wrap_func(func),
            trigger="interval",
            seconds=interval_seconds,
            id=task_id,
            **job_options,
        )

    def add_daily_task(self, task_id: str, func, hour: int, minute: int = 0):
        """
        添加一个每日定时任务（Cron）
        :param task_id: 任务唯一 ID
        :param func: 要执行的函数
        :param hour: 去执行任务的指定小时（24小时制）
        :param minute: 去执行任务的指定分钟
        """
        if self.scheduler.get_job(task_id):
            self.scheduler.remove_job(task_id)

        self.scheduler.add_job(
            self._wrap_func(func),
            trigger="cron",
            hour=hour,
            minute=minute,
            id=task_id,
            max_instances=1,
            coalesce=True,
            misfire_grace_time=60
        )

    # =========================
    # 控制
    # =========================
    def remove_task(self, task_id: str):
        """
        删除任务
        :param task_id: 要删除的任务 ID
        """
        if self.scheduler.get_job(task_id):
            self.scheduler.remove_job(task_id)

    def pause_task(self, task_id: str):
        """
        暂停任务，使其不再执行
        :param task_id: 任务 ID
        """
        job = self.scheduler.get_job(task_id)
        if job:
            job.pause()

    def resume_task(self, task_id: str):
        """
        恢复被暂停的任务
        :param task_id: 任务 ID
        """
        job = self.scheduler.get_job(task_id)
        if job:
            job.resume()

    def set_task_interval(self, task_id: str, interval_seconds: int):
        """
        修改已有 interval 任务的执行间隔
        :param task_id: 任务 ID
        :param interval_seconds: 新的执行间隔（秒）
        :return: True 表示修改成功；False 表示任务不存在
        """
        job = self.scheduler.get_job(task_id)
        if not job:
            return False

        job.reschedule(trigger="interval", seconds=interval_seconds)
        return True

    def get_job(self, task_id: str) -> Job | None:
        """
        获取 APScheduler Job 对象（用于查询任务状态）
        :param task_id: 任务 ID
        :return: Job 或 None
        """
        return self.scheduler.get_job(task_id)

    # =========================
    # 生命周期
    # =========================
    def start(self):
        """ 启动调度器(一般在 FastAPI startup 事件中调用) """
        if not self.scheduler.running:
            self.scheduler.start()

    def shutdown(self):
        """ 关闭调度器（程序退出前调用） """
        if self.scheduler.running:
            self.scheduler.shutdown()


scheduler = SchedulerManager()
