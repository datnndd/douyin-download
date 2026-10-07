// frontend/src/components/TaskTracker.tsx

import React, { useState } from 'react';
import {
  AlertCircle,
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  Cpu,
  Download,
  Loader2,
  Pause,
  Play,
  RotateCcw,
  Sparkles,
  StopCircle,
  X,
  XCircle,
} from 'lucide-react';
import { TaskDetailResponse, TaskStatus } from '../types/api';
import { api } from '../services/api';

interface TaskTrackerProps {
  tasks: TaskDetailResponse[];
  onRefresh?: () => void;
  onDismissTask?: (taskId: string) => void;
}

export const TaskTracker: React.FC<TaskTrackerProps> = ({
  tasks,
  onRefresh,
  onDismissTask,
}) => {
  const [expandedThreads, setExpandedThreads] = useState<Record<string, boolean>>({});
  const [actionLoading, setActionLoading] = useState<Record<string, boolean>>({});

  const toggleThreadView = (taskId: string) => {
    setExpandedThreads((prev) => ({
      ...prev,
      [taskId]: !prev[taskId],
    }));
  };

  const formatBytes = (bytes: number): string => {
    if (bytes <= 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  };

  const formatSpeed = (bps: number): string => {
    if (bps <= 0) return '0 KB/s';
    if (bps >= 1024 * 1024) {
      return (bps / (1024 * 1024)).toFixed(1) + ' MB/s';
    }
    return (bps / 1024).toFixed(0) + ' KB/s';
  };

  const getStatusBadge = (status: TaskStatus) => {
    switch (status) {
      case 'DOWNLOADING':
      case 'RUNNING':
        return (
          <span className="px-2.5 py-0.5 rounded-full bg-blue-50 text-blue-700 border border-blue-200 text-[11px] font-semibold flex items-center gap-1.5">
            <span className="w-1.5 h-1.5 rounded-full bg-blue-600 animate-pulse" />
            Downloading
          </span>
        );
      case 'PARSING':
      case 'PENDING':
        return (
          <span className="px-2.5 py-0.5 rounded-full bg-amber-50 text-amber-700 border border-amber-200 text-[11px] font-semibold flex items-center gap-1.5">
            <Loader2 className="w-3 h-3 animate-spin text-amber-600" />
            Queued
          </span>
        );
      case 'PAUSED':
        return (
          <span className="px-2.5 py-0.5 rounded-full bg-orange-50 text-orange-700 border border-orange-200 text-[11px] font-semibold flex items-center gap-1.5">
            <Pause className="w-3 h-3 text-orange-600" />
            Paused
          </span>
        );
      case 'COMPLETED':
        return (
          <span className="px-2.5 py-0.5 rounded-full bg-emerald-50 text-emerald-700 border border-emerald-200 text-[11px] font-semibold flex items-center gap-1.5">
            <CheckCircle2 className="w-3 h-3 text-emerald-600" />
            Completed
          </span>
        );
      case 'FAILED':
        return (
          <span className="px-2.5 py-0.5 rounded-full bg-rose-50 text-rose-700 border border-rose-200 text-[11px] font-semibold flex items-center gap-1.5">
            <XCircle className="w-3 h-3 text-rose-600" />
            Failed
          </span>
        );
      case 'CANCELLED':
        return (
          <span className="px-2.5 py-0.5 rounded-full bg-stone-100 text-stone-600 border border-stone-200 text-[11px] font-semibold flex items-center gap-1.5">
            <StopCircle className="w-3 h-3 text-stone-500" />
            Cancelled
          </span>
        );
      default:
        return (
          <span className="px-2.5 py-0.5 rounded-full bg-gray-100 text-gray-700 text-[11px] font-semibold">
            {status}
          </span>
        );
    }
  };

  const handlePause = async (taskId: string) => {
    setActionLoading((prev) => ({ ...prev, [taskId]: true }));
    try {
      await api.pauseTask(taskId);
      if (onRefresh) onRefresh();
    } catch (e) {
      console.error(e);
    } finally {
      setActionLoading((prev) => ({ ...prev, [taskId]: false }));
    }
  };

  const handleResume = async (taskId: string) => {
    setActionLoading((prev) => ({ ...prev, [taskId]: true }));
    try {
      await api.resumeTask(taskId);
      if (onRefresh) onRefresh();
    } catch (e) {
      console.error(e);
    } finally {
      setActionLoading((prev) => ({ ...prev, [taskId]: false }));
    }
  };

  const handleCancel = async (taskId: string) => {
    setActionLoading((prev) => ({ ...prev, [taskId]: true }));
    try {
      await api.cancelTask(taskId);
      if (onRefresh) onRefresh();
    } catch (e) {
      console.error(e);
    } finally {
      setActionLoading((prev) => ({ ...prev, [taskId]: false }));
    }
  };

  if (!tasks || tasks.length === 0) {
    return null;
  }

  return (
    <div className="space-y-4 pt-2">
      <div className="flex items-center justify-between">
        <h3 className="text-xs font-bold uppercase tracking-wider text-[#595E68] flex items-center space-x-1.5">
          <Download className="w-3.5 h-3.5 text-[#8D4B00]" />
          <span>Live Download Monitor ({tasks.length})</span>
        </h3>
      </div>

      <div className="space-y-4">
        {tasks.map((task) => {
          const isBusy =
            task.status === 'RUNNING' ||
            task.status === 'DOWNLOADING' ||
            task.status === 'PARSING';
          const isPaused = task.status === 'PAUSED';
          const isDone =
            task.status === 'COMPLETED' ||
            task.status === 'FAILED' ||
            task.status === 'CANCELLED';
          const isExpanded = expandedThreads[task.task_id] ?? false;

          return (
            <div
              key={task.task_id}
              className={`bg-[#FFFFFF] border rounded-2xl p-5 shadow-sm transition-all ${
                isBusy
                  ? 'border-[#8D4B00]/40 shadow-[#8D4B00]/5 ring-1 ring-[#8D4B00]/20'
                  : 'border-[#E5DED4]'
              }`}
            >
              {/* Task Header */}
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 pb-3 border-b border-[#E5DED4]">
                <div className="flex items-center space-x-2.5 overflow-hidden">
                  <span className="font-mono text-xs font-semibold text-[#1F2328] truncate max-w-xs">
                    {task.current_item || `Task: ${task.task_id.slice(0, 8)}...`}
                  </span>
                  {getStatusBadge(task.status)}
                </div>

                {/* Control buttons */}
                <div className="flex items-center space-x-2 self-end sm:self-auto">
                  {isBusy && (
                    <button
                      onClick={() => handlePause(task.task_id)}
                      disabled={actionLoading[task.task_id]}
                      className="px-2.5 py-1 rounded-lg text-xs font-medium bg-[#F3ECE2] hover:bg-[#EDE5DA] text-[#1F2328] border border-[#E5DED4] flex items-center space-x-1 transition-colors cursor-pointer"
                      title="Pause download"
                    >
                      <Pause className="w-3 h-3 text-[#8D4B00]" />
                      <span>Pause</span>
                    </button>
                  )}

                  {isPaused && (
                    <button
                      onClick={() => handleResume(task.task_id)}
                      disabled={actionLoading[task.task_id]}
                      className="px-2.5 py-1 rounded-lg text-xs font-medium bg-[#8D4B00] hover:bg-[#743D00] text-white flex items-center space-x-1 transition-colors cursor-pointer"
                      title="Resume download"
                    >
                      <Play className="w-3 h-3 text-white" />
                      <span>Resume</span>
                    </button>
                  )}

                  {(isBusy || isPaused) && (
                    <button
                      onClick={() => handleCancel(task.task_id)}
                      disabled={actionLoading[task.task_id]}
                      className="px-2.5 py-1 rounded-lg text-xs font-medium bg-rose-50 hover:bg-rose-100 text-rose-700 border border-rose-200 flex items-center space-x-1 transition-colors cursor-pointer"
                      title="Cancel task"
                    >
                      <X className="w-3 h-3" />
                      <span>Cancel</span>
                    </button>
                  )}

                  {isDone && onDismissTask && (
                    <button
                      onClick={() => onDismissTask(task.task_id)}
                      className="p-1 rounded-lg text-[#898174] hover:text-[#1F2328] hover:bg-[#F3ECE2] transition-colors"
                      title="Dismiss record"
                    >
                      <X className="w-4 h-4" />
                    </button>
                  )}
                </div>
              </div>

              {/* Main Progress Bar */}
              <div className="mt-4 space-y-2">
                <div className="flex items-center justify-between text-xs">
                  <div className="flex items-center space-x-2">
                    <span className="font-bold text-[#1F2328] text-sm">
                      {task.progress_pct.toFixed(1)}%
                    </span>
                    {task.speed_bps > 0 && (
                      <span className="text-[11px] font-mono text-[#8D4B00] font-semibold bg-[#F3ECE2] px-2 py-0.5 rounded">
                        {formatSpeed(task.speed_bps)}
                      </span>
                    )}
                  </div>
                  <div className="text-[11px] text-[#595E68] font-mono">
                    {formatBytes(task.downloaded_bytes)}
                    {task.total_bytes > 0 && ` / ${formatBytes(task.total_bytes)}`}
                    {task.total_items > 0 && ` • ${task.completed_items}/${task.total_items} items downloaded`}
                  </div>
                </div>

                <div className="w-full bg-[#E5DED4] h-2.5 rounded-full overflow-hidden">
                  <div
                    className={`h-full rounded-full transition-all duration-300 ${
                      task.status === 'COMPLETED'
                        ? 'bg-emerald-500'
                        : task.status === 'FAILED'
                        ? 'bg-rose-500'
                        : task.status === 'PAUSED'
                        ? 'bg-amber-500'
                        : 'bg-[#8D4B00]'
                    }`}
                    style={{ width: `${Math.min(100, Math.max(0, task.progress_pct))}%` }}
                  />
                </div>
              </div>

              {/* Error message banner */}
              {task.error && (
                <div className="mt-3 p-3 rounded-xl bg-rose-50 border border-rose-200 text-rose-700 text-xs flex items-center space-x-2">
                  <AlertCircle className="w-4 h-4 text-rose-600 shrink-0" />
                  <span className="flex-1">{task.error}</span>
                </div>
              )}

              {/* Worker Threads Telemetry Expand/Collapse */}
              {task.threads && task.threads.length > 0 && (
                <div className="mt-4 pt-3 border-t border-[#E5DED4]/60">
                  <button
                    type="button"
                    onClick={() => toggleThreadView(task.task_id)}
                    className="flex items-center space-x-1.5 text-[11px] font-medium text-[#595E68] hover:text-[#1F2328] transition-colors"
                  >
                    <Cpu className="w-3.5 h-3.5 text-[#8D4B00]" />
                    <span>
                      Worker Threads Status ({task.threads.length} threads • Active: {task.active_threads})
                    </span>
                    {isExpanded ? (
                      <ChevronUp className="w-3.5 h-3.5" />
                    ) : (
                      <ChevronDown className="w-3.5 h-3.5" />
                    )}
                  </button>

                  {isExpanded && (
                    <div className="mt-3 grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-2 animate-fadeIn">
                      {task.threads.map((thr) => (
                        <div
                          key={thr.thread_id}
                          className="p-2.5 rounded-xl bg-[#FAF8F5] border border-[#E5DED4] space-y-1.5"
                        >
                          <div className="flex items-center justify-between text-[11px]">
                            <span className="font-mono font-semibold text-[#1F2328]">
                              Worker #{thr.thread_id}
                            </span>
                            <span
                              className={`px-1.5 py-0.2 rounded text-[10px] font-mono ${
                                thr.status === 'DOWNLOADING'
                                  ? 'bg-blue-100 text-blue-700 font-bold'
                                  : 'bg-stone-200 text-stone-600'
                              }`}
                            >
                              {thr.status}
                            </span>
                          </div>

                          <div className="w-full bg-[#E5DED4] h-1.5 rounded-full overflow-hidden">
                            <div
                              className="bg-[#8D4B00] h-full rounded-full transition-all duration-200"
                              style={{ width: `${thr.pct}%` }}
                            />
                          </div>

                          <div className="flex items-center justify-between text-[10px] text-[#595E68] font-mono">
                            <span className="truncate max-w-[120px]">
                              {thr.current_file || 'Idle'}
                            </span>
                            <span>{thr.speed_bps > 0 ? formatSpeed(thr.speed_bps) : `${thr.pct.toFixed(0)}%`}</span>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
};
