// frontend/src/App.tsx

import React, { useEffect, useState } from 'react';
import { Header } from './components/Header';
import { UnifiedDownloader } from './components/UnifiedDownloader';
import { TaskTracker } from './components/TaskTracker';
import { MediaLibrary } from './components/MediaLibrary';
import { SettingsModal } from './components/SettingsModal';
import {
  DownloadProgressEvent,
  SettingsModel,
  TaskDetailResponse,
  TaskResponse,
} from './types/api';
import { api } from './services/api';

export const App: React.FC = () => {
  const [activeTab, setActiveTab] = useState<'downloader' | 'library'>('downloader');
  const [tasks, setTasks] = useState<TaskDetailResponse[]>([]);
  const [settings, setSettings] = useState<SettingsModel | null>(null);
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);
  const [backendHealthy, setBackendHealthy] = useState(true);

  // Initial load
  useEffect(() => {
    loadSettings();
    loadTasks();
    checkHealth();

    // Check health periodically
    const healthInterval = setInterval(checkHealth, 10000);
    return () => clearInterval(healthInterval);
  }, []);

  // Polling backup for task list
  useEffect(() => {
    const hasActiveTasks = tasks.some(
      (t) =>
        t.status === 'RUNNING' ||
        t.status === 'DOWNLOADING' ||
        t.status === 'PENDING' ||
        t.status === 'PARSING'
    );

    const intervalTime = hasActiveTasks ? 2000 : 8000;
    const taskInterval = setInterval(() => {
      loadTasks();
    }, intervalTime);

    return () => clearInterval(taskInterval);
  }, [tasks]);

  // Subscribe to SSE real-time stream
  useEffect(() => {
    const unsubscribe = api.subscribeToStream(
      (event: DownloadProgressEvent) => {
        setTasks((prev) => {
          const index = prev.findIndex((t) => t.task_id === event.task_id);
          const updatedRecord: TaskDetailResponse = {
            task_id: event.task_id,
            status: event.status,
            progress_pct: event.progress_pct,
            downloaded_bytes: event.downloaded_bytes,
            total_bytes: event.total_bytes,
            speed_bps: event.speed_bps,
            current_item: event.item_title,
            completed_items: event.item_index,
            total_items: event.item_total,
            active_threads: event.active_threads,
            threads: event.threads || [],
            error: undefined,
            created_at: new Date().toISOString(),
            updated_at: event.timestamp || new Date().toISOString(),
          };

          if (index >= 0) {
            const next = [...prev];
            next[index] = {
              ...next[index],
              ...updatedRecord,
              created_at: next[index].created_at, // keep original
            };
            return next;
          } else {
            return [updatedRecord, ...prev];
          }
        });
      },
      (err) => {
        // SSE error, gracefully fall back to interval polling
        console.debug('SSE disconnected, using polling fallback', err);
      }
    );

    return () => {
      unsubscribe();
    };
  }, []);

  const checkHealth = async () => {
    try {
      const res = await api.getHealth();
      setBackendHealthy(res.status === 'ok');
    } catch {
      setBackendHealthy(false);
    }
  };

  const loadSettings = async () => {
    try {
      const data = await api.getSettings();
      setSettings(data);
    } catch (e) {
      console.warn('Could not load settings:', e);
    }
  };

  const loadTasks = async () => {
    try {
      const data = await api.getTasks();
      setTasks(data);
    } catch (e) {
      console.warn('Could not load tasks:', e);
    }
  };

  const handleOpenFolder = async () => {
    try {
      await api.openFolder('');
    } catch (e) {
      console.error('Failed to open folder:', e);
    }
  };

  const handleDownloadStarted = (task: TaskResponse) => {
    // Add pending task to tracker
    const newTask: TaskDetailResponse = {
      task_id: task.task_id,
      status: task.status,
      progress_pct: 0,
      downloaded_bytes: 0,
      total_bytes: 0,
      speed_bps: 0,
      current_item: task.message || 'New task',
      completed_items: 0,
      total_items: 1,
      active_threads: 0,
      threads: [],
      created_at: task.created_at || new Date().toISOString(),
      updated_at: new Date().toISOString(),
    };
    setTasks((prev) => [newTask, ...prev]);
  };

  const handleDismissTask = (taskId: string) => {
    setTasks((prev) => prev.filter((t) => t.task_id !== taskId));
  };

  const activeRunningCount = tasks.filter(
    (t) =>
      t.status === 'RUNNING' ||
      t.status === 'DOWNLOADING' ||
      t.status === 'PENDING' ||
      t.status === 'PARSING'
  ).length;

  return (
    <div className="min-h-screen bg-[#FAF8F5] text-[#1F2328] flex flex-col font-sans">
      <Header
        activeTab={activeTab}
        setActiveTab={setActiveTab}
        onOpenSettings={() => setIsSettingsOpen(true)}
        onOpenFolder={handleOpenFolder}
        activeTaskCount={activeRunningCount}
        isBackendHealthy={backendHealthy}
      />

      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 py-6 space-y-6">
        {activeTab === 'downloader' ? (
          <>
            <UnifiedDownloader
              settings={settings}
              onDownloadStarted={handleDownloadStarted}
              onOpenFolder={handleOpenFolder}
            />

            {/* Live Task Tracker section */}
            <TaskTracker
              tasks={tasks}
              onRefresh={loadTasks}
              onDismissTask={handleDismissTask}
            />
          </>
        ) : (
          <MediaLibrary onOpenFolder={handleOpenFolder} />
        )}
      </main>

      <SettingsModal
        isOpen={isSettingsOpen}
        onClose={() => setIsSettingsOpen(false)}
        onSaved={(newSettings) => setSettings(newSettings)}
      />

      <footer className="border-t border-[#E5DED4] py-4 px-6 text-center text-xs text-[#898174]">
        <span>Douyin Web Downloader • FastAPI & React 19 Editorial Edition</span>
      </footer>
    </div>
  );
};
