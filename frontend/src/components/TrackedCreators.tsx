// frontend/src/components/TrackedCreators.tsx

import React, { useEffect, useState } from 'react';
import {
  AlertCircle,
  ArrowRight,
  Check,
  ChevronDown,
  ChevronUp,
  Download,
  ExternalLink,
  Film,
  Loader2,
  Plus,
  RefreshCw,
  Sparkles,
  Trash2,
  User,
  Users,
} from 'lucide-react';
import { TrackedCreator, TaskResponse } from '../types/api';
import { api } from '../services/api';

interface TrackedCreatorsProps {
  onDownloadStarted: (task: TaskResponse) => void;
  onRefreshStats?: () => void;
}

export const TrackedCreators: React.FC<TrackedCreatorsProps> = ({
  onDownloadStarted,
  onRefreshStats,
}) => {
  const [creators, setCreators] = useState<TrackedCreator[]>([]);
  const [loading, setLoading] = useState(true);
  const [checkingAll, setCheckingAll] = useState(false);
  const [updatingAll, setUpdatingAll] = useState(false);
  const [checkingSecUid, setCheckingSecUid] = useState<string | null>(null);
  const [updatingSecUid, setUpdatingSecUid] = useState<string | null>(null);
  const [newUrlInput, setNewUrlInput] = useState('');
  const [enrolling, setEnrolling] = useState(false);
  const [enrollError, setEnrollError] = useState<string | null>(null);
  const [expandedSecUid, setExpandedSecUid] = useState<string | null>(null);

  useEffect(() => {
    loadCreators();
  }, []);

  const loadCreators = async () => {
    setLoading(true);
    try {
      const data = await api.getTrackedCreators();
      setCreators(data);
    } catch (e) {
      console.error('Failed to load tracked creators:', e);
    } finally {
      setLoading(false);
    }
  };

  const handleTrackNew = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newUrlInput.trim()) return;

    setEnrolling(true);
    setEnrollError(null);
    try {
      await api.trackCreator({ url: newUrlInput.trim() });
      setNewUrlInput('');
      await loadCreators();
      if (onRefreshStats) onRefreshStats();
    } catch (err: any) {
      setEnrollError(err.message || 'Failed to track creator. Please check the URL.');
    } finally {
      setEnrolling(false);
    }
  };

  const handleCheckOne = async (secUid: string) => {
    setCheckingSecUid(secUid);
    try {
      const updated = await api.checkCreatorUpdates(secUid);
      setCreators((prev) =>
        prev.map((c) => (c.sec_uid === secUid ? updated : c))
      );
      if (onRefreshStats) onRefreshStats();
    } catch (err: any) {
      alert(`Check failed: ${err.message}`);
    } finally {
      setCheckingSecUid(null);
    }
  };

  const handleCheckAll = async () => {
    setCheckingAll(true);
    try {
      await api.checkAllCreatorUpdates();
      await loadCreators();
      if (onRefreshStats) onRefreshStats();
    } catch (err: any) {
      alert(`Check all failed: ${err.message}`);
    } finally {
      setCheckingAll(false);
    }
  };

  const handleUpdateOne = async (secUid: string) => {
    setUpdatingSecUid(secUid);
    try {
      const task = await api.updateCreatorVideos(secUid);
      onDownloadStarted(task);
      // Optimistically update creator state
      setCreators((prev) =>
        prev.map((c) =>
          c.sec_uid === secUid ? { ...c, pending_new_count: 0, pending_videos: [] } : c
        )
      );
      if (onRefreshStats) onRefreshStats();
    } catch (err: any) {
      alert(`Update failed: ${err.message}`);
    } finally {
      setUpdatingSecUid(null);
    }
  };

  const handleUpdateAll = async () => {
    setUpdatingAll(true);
    try {
      const tasks = await api.updateAllTrackedCreators();
      for (const t of tasks) {
        onDownloadStarted(t);
      }
      await loadCreators();
      if (onRefreshStats) onRefreshStats();
    } catch (err: any) {
      alert(`Update all failed: ${err.message}`);
    } finally {
      setUpdatingAll(false);
    }
  };

  const handleUntrack = async (secUid: string, nickname?: string) => {
    const confirmMsg = `Are you sure you want to untrack ${nickname || 'this creator'}? Tracking history will be deleted.`;
    if (!window.confirm(confirmMsg)) return;

    try {
      await api.untrackCreator(secUid);
      setCreators((prev) => prev.filter((c) => c.sec_uid !== secUid));
      if (onRefreshStats) onRefreshStats();
    } catch (err: any) {
      alert(`Untrack failed: ${err.message}`);
    }
  };

  const totalPending = creators.reduce((acc, c) => acc + (c.pending_new_count || 0), 0);

  return (
    <div className="space-y-6 animate-fadeIn">
      {/* Top Header Card */}
      <div className="p-6 bg-white rounded-2xl border border-[#E5DED4] shadow-xs flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center space-x-2.5">
            <div className="w-9 h-9 rounded-xl bg-[#8D4B00]/10 flex items-center justify-center text-[#8D4B00]">
              <Users className="w-5 h-5 stroke-[2.2]" />
            </div>
            <div>
              <h2 className="text-lg font-bold text-[#1F2328]">Tracked Creators</h2>
              <p className="text-xs text-[#595E68]">
                Monitor creator uploads with zero-bloat metadata and download newly detected videos in 1-Click.
              </p>
            </div>
          </div>
        </div>

        {/* Global Action Buttons */}
        <div className="flex items-center space-x-2.5 shrink-0">
          <button
            onClick={handleCheckAll}
            disabled={checkingAll || creators.length === 0}
            className="flex items-center space-x-1.5 px-3.5 py-2 rounded-xl text-xs font-semibold bg-[#F3ECE2] hover:bg-[#EDE5DA] text-[#1F2328] border border-[#E5DED4] transition-colors disabled:opacity-50 cursor-pointer"
            title="Poll upstream Douyin API for new uploads across all tracked creators"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${checkingAll ? 'animate-spin text-[#8D4B00]' : ''}`} />
            <span>{checkingAll ? 'Checking All...' : 'Check All'}</span>
          </button>

          <button
            onClick={handleUpdateAll}
            disabled={updatingAll || totalPending === 0}
            className="flex items-center space-x-1.5 px-4 py-2 rounded-xl text-xs font-semibold bg-[#8D4B00] hover:bg-[#723C00] text-white shadow-xs transition-all disabled:opacity-40 cursor-pointer"
            title="Download newly added videos for all creators"
          >
            {updatingAll ? (
              <Loader2 className="w-3.5 h-3.5 animate-spin" />
            ) : (
              <Download className="w-3.5 h-3.5" />
            )}
            <span>
              {updatingAll ? 'Updating...' : `Update All (${totalPending} new)`}
            </span>
          </button>
        </div>
      </div>

      {/* Quick Enroll Bar */}
      <form
        onSubmit={handleTrackNew}
        className="p-4 bg-white rounded-2xl border border-[#E5DED4] shadow-xs flex flex-col sm:flex-row items-center gap-3"
      >
        <div className="relative flex-1 w-full">
          <input
            type="text"
            value={newUrlInput}
            onChange={(e) => setNewUrlInput(e.target.value)}
            placeholder="Paste creator homepage URL (e.g. https://www.douyin.com/user/MS4wLjAB...) to track"
            className="w-full px-4 py-2.5 rounded-xl border border-[#E5DED4] bg-[#FAF8F5] text-xs text-[#1F2328] placeholder-[#898174] focus:outline-hidden focus:border-[#8D4B00] focus:ring-1 focus:ring-[#8D4B00] transition-all"
            disabled={enrolling}
          />
        </div>
        <button
          type="submit"
          disabled={enrolling || !newUrlInput.trim()}
          className="w-full sm:w-auto flex items-center justify-center space-x-1.5 px-5 py-2.5 rounded-xl text-xs font-semibold bg-[#8D4B00] hover:bg-[#723C00] text-white transition-all disabled:opacity-50 cursor-pointer shrink-0"
        >
          {enrolling ? (
            <Loader2 className="w-3.5 h-3.5 animate-spin" />
          ) : (
            <Plus className="w-3.5 h-3.5" />
          )}
          <span>{enrolling ? 'Tracking...' : 'Track Creator'}</span>
        </button>
      </form>

      {enrollError && (
        <div className="p-3 bg-rose-50 border border-rose-200 rounded-xl text-xs text-rose-700 flex items-center space-x-2 animate-fadeIn">
          <AlertCircle className="w-4 h-4 shrink-0 text-rose-600" />
          <span>{enrollError}</span>
        </div>
      )}

      {/* Creators Grid / Empty State */}
      {loading ? (
        <div className="py-16 text-center text-[#595E68] flex flex-col items-center justify-center space-y-3">
          <Loader2 className="w-8 h-8 animate-spin text-[#8D4B00]" />
          <p className="text-xs">Loading tracked creators...</p>
        </div>
      ) : creators.length === 0 ? (
        <div className="py-16 px-4 bg-white rounded-2xl border border-[#E5DED4] text-center space-y-4">
          <div className="w-14 h-14 mx-auto rounded-2xl bg-[#F3ECE2] flex items-center justify-center text-[#8D4B00]">
            <Users className="w-7 h-7 stroke-[1.8]" />
          </div>
          <div className="max-w-md mx-auto space-y-1.5">
            <h3 className="text-sm font-bold text-[#1F2328]">No creators tracked yet</h3>
            <p className="text-xs text-[#595E68] leading-relaxed">
              Paste a Douyin creator URL in the box above or click{' '}
              <span className="font-semibold text-[#8D4B00]">+ Track Creator</span> on any profile preview card in the Downloader to start tracking new uploads.
            </p>
          </div>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {creators.map((c) => {
            const hasPending = (c.pending_new_count || 0) > 0;
            const isUpdating = updatingSecUid === c.sec_uid;
            const isChecking = checkingSecUid === c.sec_uid;
            const isExpanded = expandedSecUid === c.sec_uid;

            return (
              <div
                key={c.sec_uid}
                className={`p-4 bg-white rounded-2xl border transition-all duration-200 flex flex-col justify-between ${
                  hasPending
                    ? 'border-[#8D4B00]/40 shadow-sm ring-1 ring-[#8D4B00]/10'
                    : 'border-[#E5DED4] hover:border-[#D5CDBD]'
                }`}
              >
                <div>
                  {/* Top Creator Info */}
                  <div className="flex items-start gap-3">
                    <img
                      src={c.avatar_thumb || '/avatar-placeholder.png'}
                      alt={c.nickname || 'Creator'}
                      className="w-12 h-12 rounded-full object-cover border border-[#E5DED4] shrink-0 bg-[#FAF8F5]"
                      onError={(e) => {
                        (e.target as HTMLElement).style.display = 'none';
                      }}
                    />
                    <div className="overflow-hidden flex-1 min-w-0">
                      <div className="flex items-center justify-between gap-1">
                        <h4 className="text-xs font-bold text-[#1F2328] truncate">
                          {c.nickname || 'Douyin Creator'}
                        </h4>
                        <button
                          onClick={() => handleUntrack(c.sec_uid, c.nickname)}
                          className="text-[#898174] hover:text-rose-600 p-1 rounded-md transition-colors"
                          title="Untrack this creator"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      </div>
                      <p className="text-[10px] text-[#595E68] font-mono truncate">
                        {c.unique_id ? `@${c.unique_id}` : `ID: ${c.sec_uid.slice(0, 14)}...`}
                      </p>
                    </div>
                  </div>

                  {/* Status Banner */}
                  <div className="mt-3.5">
                    {hasPending ? (
                      <div className="flex items-center justify-between p-2.5 rounded-xl bg-[#F3ECE2] border border-[#8D4B00]/30 text-[#8D4B00]">
                        <div className="flex items-center space-x-1.5">
                          <Sparkles className="w-3.5 h-3.5 shrink-0" />
                          <span className="text-xs font-bold font-mono">
                            {c.pending_new_count} NEW {c.pending_new_count === 1 ? 'VIDEO' : 'VIDEOS'}
                          </span>
                        </div>
                        <span className="text-[10px] font-medium bg-[#8D4B00] text-white px-2 py-0.5 rounded-full">
                          Ready to Update
                        </span>
                      </div>
                    ) : (
                      <div className="flex items-center space-x-1.5 p-2 rounded-xl bg-[#FAF8F5] border border-[#E5DED4] text-[#595E68]">
                        <Check className="w-3.5 h-3.5 text-emerald-600 shrink-0" />
                        <span className="text-xs font-medium">Up to date</span>
                      </div>
                    )}
                  </div>

                  {/* Timestamps & Info */}
                  <div className="mt-3 text-[10px] text-[#898174] space-y-1">
                    <div className="flex justify-between">
                      <span>Last checked:</span>
                      <span className="font-mono text-[#595E68]">
                        {c.last_checked_at ? c.last_checked_at.slice(0, 19).replace('T', ' ') : 'Never'}
                      </span>
                    </div>
                    {c.last_downloaded_at && (
                      <div className="flex justify-between">
                        <span>Last downloaded:</span>
                        <span className="font-mono text-[#595E68]">
                          {c.last_downloaded_at.slice(0, 19).replace('T', ' ')}
                        </span>
                      </div>
                    )}
                  </div>

                  {/* Expand Pending Videos Details */}
                  {hasPending && c.pending_videos && c.pending_videos.length > 0 && (
                    <div className="mt-2.5">
                      <button
                        type="button"
                        onClick={() =>
                          setExpandedSecUid(isExpanded ? null : c.sec_uid)
                        }
                        className="flex items-center space-x-1 text-[11px] text-[#8D4B00] font-semibold hover:underline"
                      >
                        <span>{isExpanded ? 'Hide pending items' : 'View pending items'}</span>
                        {isExpanded ? (
                          <ChevronUp className="w-3 h-3" />
                        ) : (
                          <ChevronDown className="w-3 h-3" />
                        )}
                      </button>

                      {isExpanded && (
                        <div className="mt-2 p-2 rounded-lg bg-[#FAF8F5] border border-[#E5DED4] max-h-36 overflow-y-auto space-y-1.5 text-[11px]">
                          {c.pending_videos.map((v) => (
                            <div
                              key={v.aweme_id}
                              className="p-1.5 bg-white rounded-md border border-[#E5DED4] flex items-center justify-between gap-2"
                            >
                              <span className="truncate text-[#1F2328]" title={v.title}>
                                {v.title || `Video ${v.aweme_id}`}
                              </span>
                              <span className="text-[9px] font-mono text-[#898174] shrink-0">
                                {v.aweme_id.slice(-6)}
                              </span>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  )}
                </div>

                {/* Card Actions */}
                <div className="mt-4 pt-3 border-t border-[#E5DED4] flex items-center gap-2">
                  {hasPending ? (
                    <button
                      onClick={() => handleUpdateOne(c.sec_uid)}
                      disabled={isUpdating}
                      className="flex-1 flex items-center justify-center space-x-1.5 px-3 py-2 rounded-xl text-xs font-bold bg-[#8D4B00] hover:bg-[#723C00] text-white shadow-xs transition-all disabled:opacity-50 cursor-pointer"
                    >
                      {isUpdating ? (
                        <Loader2 className="w-3.5 h-3.5 animate-spin" />
                      ) : (
                        <Download className="w-3.5 h-3.5" />
                      )}
                      <span>
                        {isUpdating ? 'Updating...' : `UPDATE (${c.pending_new_count} NEW)`}
                      </span>
                    </button>
                  ) : (
                    <button
                      onClick={() => handleCheckOne(c.sec_uid)}
                      disabled={isChecking}
                      className="flex-1 flex items-center justify-center space-x-1.5 px-3 py-2 rounded-xl text-xs font-semibold bg-[#F3ECE2] hover:bg-[#EDE5DA] text-[#1F2328] border border-[#E5DED4] transition-all disabled:opacity-50 cursor-pointer"
                    >
                      <RefreshCw className={`w-3.5 h-3.5 ${isChecking ? 'animate-spin text-[#8D4B00]' : ''}`} />
                      <span>{isChecking ? 'Checking...' : 'Check Updates'}</span>
                    </button>
                  )}

                  {hasPending && (
                    <button
                      onClick={() => handleCheckOne(c.sec_uid)}
                      disabled={isChecking}
                      className="p-2 rounded-xl bg-[#F3ECE2] hover:bg-[#EDE5DA] text-[#1F2328] border border-[#E5DED4] transition-colors disabled:opacity-50 cursor-pointer"
                      title="Re-check this creator"
                    >
                      <RefreshCw className={`w-3.5 h-3.5 ${isChecking ? 'animate-spin' : ''}`} />
                    </button>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};
