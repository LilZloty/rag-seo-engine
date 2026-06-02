import { useState, useEffect, useCallback, useRef } from 'react';
import { taskAPI, TaskStatus } from '../lib/api';

interface UseTaskPollingOptions {
    /** Polling interval in ms (default 2000) */
    interval?: number;
    /** Callback when task completes successfully */
    onSuccess?: (result: unknown) => void;
    /** Callback when task fails */
    onError?: (error: string) => void;
}

interface UseTaskPollingReturn {
    /** Start polling a task */
    startPolling: (taskId: string) => void;
    /** Stop polling */
    stopPolling: () => void;
    /** Current task status */
    status: TaskStatus | null;
    /** Whether we're actively polling */
    isPolling: boolean;
    /** Whether the task is complete (success or failure) */
    isComplete: boolean;
    /** Progress info if available */
    progress: TaskStatus['progress'];
}

export function useTaskPolling(options: UseTaskPollingOptions = {}): UseTaskPollingReturn {
    const { interval = 2000, onSuccess, onError } = options;
    const [status, setStatus] = useState<TaskStatus | null>(null);
    const [isPolling, setIsPolling] = useState(false);
    const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
    const taskIdRef = useRef<string | null>(null);
    const callbacksRef = useRef({ onSuccess, onError });
    callbacksRef.current = { onSuccess, onError };

    const stopPolling = useCallback(() => {
        if (intervalRef.current) {
            clearInterval(intervalRef.current);
            intervalRef.current = null;
        }
        taskIdRef.current = null;
        setIsPolling(false);
    }, []);

    const poll = useCallback(async (taskId: string) => {
        try {
            const result = await taskAPI.getStatus(taskId);
            setStatus(result);

            if (result.status === 'SUCCESS') {
                stopPolling();
                callbacksRef.current.onSuccess?.(result.result);
            } else if (result.status === 'FAILURE') {
                stopPolling();
                callbacksRef.current.onError?.(String(result.result || 'Task failed'));
            }
        } catch {
            // Network error — keep polling, it may recover
        }
    }, [stopPolling]);

    const startPolling = useCallback((taskId: string) => {
        // Clean up previous polling
        if (intervalRef.current) {
            clearInterval(intervalRef.current);
        }
        taskIdRef.current = taskId;
        setIsPolling(true);
        setStatus({ task_id: taskId, status: 'PENDING', result: null, progress: null });

        // Poll immediately, then on interval
        poll(taskId);
        intervalRef.current = setInterval(() => {
            if (taskIdRef.current === taskId) {
                poll(taskId);
            }
        }, interval);
    }, [poll, interval]);

    // Cleanup on unmount
    useEffect(() => {
        return () => {
            if (intervalRef.current) {
                clearInterval(intervalRef.current);
            }
        };
    }, []);

    const isComplete = status?.status === 'SUCCESS' || status?.status === 'FAILURE';

    return {
        startPolling,
        stopPolling,
        status,
        isPolling,
        isComplete,
        progress: status?.progress ?? null,
    };
}
