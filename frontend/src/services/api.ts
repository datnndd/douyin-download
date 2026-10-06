// frontend/src/services/api.ts

import {
  DownloadProgressEvent,
  DownloadRequest,
  HealthResponse,
  MediaListResponse,
  OpenFolderResponse,
  ParseRequest,
  ParseResponse,
  SettingsModel,
  TaskDetailResponse,
  TaskResponse,
} from '../types/api';

const BASE_URL = '';

async function handleResponse<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let errorDetail = `HTTP Error ${res.status}: ${res.statusText}`;
    try {
      const data = await res.json();
      if (data && data.detail) {
        errorDetail = typeof data.detail === 'string' ? data.detail : JSON.stringify(data.detail);
      }
    } catch {
      // not json
    }
    throw new Error(errorDetail);
  }
  return res.json() as Promise<T>;
}

export const api = {
  async parseUrl(url: string, cookie?: string): Promise<ParseResponse> {
    const payload: ParseRequest = { url, cookie };
    const res = await fetch(`${BASE_URL}/api/parse`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    return handleResponse<ParseResponse>(res);
  },

  async startDownload(request: DownloadRequest): Promise<TaskResponse> {
    const res = await fetch(`${BASE_URL}/api/download`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(request),
    });
    return handleResponse<TaskResponse>(res);
  },

  async getTasks(): Promise<TaskDetailResponse[]> {
    const res = await fetch(`${BASE_URL}/api/tasks`);
    return handleResponse<TaskDetailResponse[]>(res);
  },

  async getTask(taskId: string): Promise<TaskDetailResponse> {
    const res = await fetch(`${BASE_URL}/api/tasks/${taskId}`);
    return handleResponse<TaskDetailResponse>(res);
  },

  async pauseTask(taskId: string): Promise<{ task_id: string; status: string }> {
    const res = await fetch(`${BASE_URL}/api/tasks/${taskId}/pause`, {
      method: 'POST',
    });
    return handleResponse<{ task_id: string; status: string }>(res);
  },

  async resumeTask(taskId: string): Promise<{ task_id: string; status: string }> {
    const res = await fetch(`${BASE_URL}/api/tasks/${taskId}/resume`, {
      method: 'POST',
    });
    return handleResponse<{ task_id: string; status: string }>(res);
  },

  async cancelTask(taskId: string): Promise<{ task_id: string; status: string }> {
    const res = await fetch(`${BASE_URL}/api/tasks/${taskId}/cancel`, {
      method: 'POST',
    });
    return handleResponse<{ task_id: string; status: string }>(res);
  },

  async getSettings(): Promise<SettingsModel> {
    const res = await fetch(`${BASE_URL}/api/settings`);
    return handleResponse<SettingsModel>(res);
  },

  async saveSettings(settings: SettingsModel): Promise<SettingsModel> {
    const res = await fetch(`${BASE_URL}/api/settings`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(settings),
    });
    return handleResponse<SettingsModel>(res);
  },

  async getMedia(): Promise<MediaListResponse> {
    const res = await fetch(`${BASE_URL}/api/media`);
    return handleResponse<MediaListResponse>(res);
  },

  async openFolder(path: string = ''): Promise<OpenFolderResponse> {
    const res = await fetch(`${BASE_URL}/api/open-folder`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ path }),
    });
    return handleResponse<OpenFolderResponse>(res);
  },

  async getHealth(): Promise<HealthResponse> {
    const res = await fetch(`${BASE_URL}/api/health`);
    return handleResponse<HealthResponse>(res);
  },

  subscribeToStream(
    onEvent: (event: DownloadProgressEvent) => void,
    onError?: (err: any) => void
  ): () => void {
    let eventSource: EventSource | null = null;
    let isClosed = false;

    try {
      eventSource = new EventSource(`${BASE_URL}/api/stream`);

      eventSource.onmessage = (e) => {
        if (isClosed) return;
        try {
          const data = JSON.parse(e.data);
          onEvent(data);
        } catch (err) {
          console.warn('Failed to parse SSE message:', err, e.data);
        }
      };

      eventSource.onerror = (err) => {
        if (isClosed) return;
        if (onError) onError(err);
      };
    } catch (e) {
      if (onError) onError(e);
    }

    return () => {
      isClosed = true;
      if (eventSource) {
        eventSource.close();
      }
    };
  },
};
