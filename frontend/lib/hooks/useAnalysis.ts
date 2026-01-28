/**
 * Custom React Query hooks for incident analysis
 * 
 * Features:
 * - Automatic caching
 * - Background refetching
 * - Optimistic updates
 * - Error retry logic
 * - Loading states
 */

import { useQuery, useMutation, useQueryClient, UseQueryOptions } from '@tanstack/react-query';
import { 
  analyzeIncident, 
  getAnalysis, 
  checkHealth, 
  getStats,
  listMcpServers,
  createPlan,
  getSettings,
  updateSettings,
  AnalysisRequest,
  AnalysisResponse,
  HealthResponse,
  SettingsResponse,
} from '@/lib/api';
import { toast } from 'sonner';

// Query keys for cache management
export const queryKeys = {
  health: ['health'] as const,
  stats: ['stats'] as const,
  mcpServers: ['mcp-servers'] as const,
  settings: ['settings'] as const,
  analysis: (id: string) => ['analysis', id] as const,
  analyses: ['analyses'] as const,
  plan: (query: string) => ['plan', query] as const,
};

/**
 * Hook for checking API health
 * - Refetches every 30 seconds
 * - 3 retry attempts
 * - Cached for performance
 */
export function useHealth() {
  return useQuery({
    queryKey: queryKeys.health,
    queryFn: checkHealth,
    staleTime: 30000, // 30 seconds
    refetchInterval: 30000, // Refetch every 30 seconds
    retry: 3,
    retryDelay: (attemptIndex) => Math.min(1000 * 2 ** attemptIndex, 10000),
  });
}

/**
 * Hook for getting API statistics
 * - Refetches on window focus
 * - 5 minute cache
 */
export function useStats() {
  return useQuery({
    queryKey: queryKeys.stats,
    queryFn: getStats,
    staleTime: 5 * 60 * 1000, // 5 minutes
    refetchOnWindowFocus: true,
  });
}

/**
 * Hook for listing MCP servers
 * - Cached indefinitely (rarely changes)
 * - Manual refetch only
 */
export function useMcpServers() {
  return useQuery({
    queryKey: queryKeys.mcpServers,
    queryFn: listMcpServers,
    staleTime: Infinity, // Never stale
    refetchOnWindowFocus: false,
    refetchOnReconnect: false,
  });
}

/**
 * Hook for fetching backend settings (configuration)
 */
export function useSettings() {
  return useQuery({
    queryKey: queryKeys.settings,
    queryFn: getSettings,
    staleTime: 0, // Always refetch when opening Settings
  });
}

/**
 * Mutation for updating backend settings
 */
export function useUpdateSettings() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (values: Record<string, string | number | boolean>) => updateSettings(values),
    onSuccess: (data: SettingsResponse) => {
      queryClient.setQueryData(queryKeys.settings, data);
      toast.success('Settings saved');
    },
    onError: (err: { message?: string; response?: { data?: { detail?: string } } }) => {
      const msg = err?.response?.data?.detail || err?.message || 'Failed to save settings';
      toast.error(typeof msg === 'string' ? msg : JSON.stringify(msg));
    },
  });
}

/**
 * Hook for fetching a specific analysis by ID
 * - Cached for 10 minutes
 * - Background refetch
 */
export function useAnalysis(analysisId: string | null, options?: UseQueryOptions<AnalysisResponse>) {
  return useQuery({
    queryKey: queryKeys.analysis(analysisId || ''),
    queryFn: () => getAnalysis(analysisId!),
    enabled: !!analysisId, // Only fetch if ID provided
    staleTime: 10 * 60 * 1000, // 10 minutes
    ...options,
  });
}

/**
 * Hook for creating an execution plan
 * - Useful for previewing analysis requirements
 */
export function usePlan(query: string, timestamp: string, enabled: boolean = false) {
  return useQuery({
    queryKey: queryKeys.plan(query),
    queryFn: () => createPlan(query, timestamp),
    enabled: enabled && !!query && !!timestamp,
    staleTime: 5 * 60 * 1000, // 5 minutes
  });
}

/**
 * Mutation hook for analyzing incidents
 * - Optimistic updates
 * - Cache invalidation
 * - Toast notifications
 * - Error handling
 */
import { useState } from 'react';

export function useAnalyzeIncident() {
  const queryClient = useQueryClient();
  // Add local state to track the stream progress
  const [streamStatus, setStreamStatus] = useState<string | null>(null);

  const mutation = useMutation({
    mutationFn: (variables: AnalysisRequest) => 
      analyzeIncident(variables, (progress) => {
        // This now triggers a re-render!
        setStreamStatus(progress.node || progress.message);
      }),
    
    onMutate: () => {
      setStreamStatus('Initializing...');
      toast.loading('Analyzing...', { id: 'analyzing' });
    },

    onSuccess: (data) => {
      setStreamStatus(null); // Clear on success
      toast.dismiss('analyzing');
      queryClient.setQueryData(queryKeys.analysis(data.analysis_id), data);
    },

    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    onError: (error: any) => {
      setStreamStatus(null);
      toast.dismiss('analyzing');
    }
  });

  return { ...mutation, streamStatus };
}
/**
 * Hook for managing analysis history in memory
 * Uses React Query's cache as the source of truth
 */
export function useAnalysisHistory() {
  const queryClient = useQueryClient();
  
  // Get all cached analyses
  const getCachedAnalyses = (): AnalysisResponse[] => {
    const cache = queryClient.getQueryCache();
    const analyses: AnalysisResponse[] = [];
    
    cache.getAll().forEach((query) => {
      if (query.queryKey[0] === 'analysis' && query.state.data) {
        analyses.push(query.state.data as AnalysisResponse);
      }
    });
    
    // Sort by timestamp (newest first)
    return analyses.sort((a, b) => {
      const timeA = parseInt(a.analysis_id.split('_')[1]);
      const timeB = parseInt(b.analysis_id.split('_')[1]);
      return timeB - timeA;
    });
  };
  
  return {
    analyses: getCachedAnalyses(),
    clearHistory: () => {
      queryClient.removeQueries({ queryKey: ['analysis'] });
      toast.success('History cleared');
    },
  };
}

/**
 * Hook for prefetching an analysis
 * Useful for hover previews
 */
export function usePrefetchAnalysis() {
  const queryClient = useQueryClient();
  
  return (analysisId: string) => {
    queryClient.prefetchQuery({
      queryKey: queryKeys.analysis(analysisId),
      queryFn: () => getAnalysis(analysisId),
      staleTime: 10 * 60 * 1000,
    });
  };
}

/**
 * Hook for streaming analysis progress
 * Uses SSE (Server-Sent Events) with React Query
 */
export function useAnalysisStream(request: AnalysisRequest | null) {
  return useQuery({
    queryKey: ['analysis-stream', request?.query],
    queryFn: async () => {
      if (!request) return null;
      
      const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
      const eventSource = new EventSource(
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        `${API_BASE_URL}/analyze/stream?${new URLSearchParams(request as any)}`
      );
      
      return new Promise((resolve, reject) => {
        const events: unknown[] = [];
        
        eventSource.onmessage = (event) => {
          const data = JSON.parse(event.data);
          events.push(data);
          
          if (data.stage === 'complete') {
            eventSource.close();
            resolve(events);
          }
          
          if (data.stage === 'error') {
            eventSource.close();
            reject(new Error(data.error));
          }
        };
        
        eventSource.onerror = () => {
          eventSource.close();
          reject(new Error('Stream connection failed'));
        };
      });
    },
    enabled: !!request,
    staleTime: 0, // Never cache streams
    refetchOnWindowFocus: false,
  });
}

/**
 * Hook for batch operations
 * Useful for comparing multiple analyses
 */
export function useBatchAnalyses(analysisIds: string[]) {
  return useQuery({
    queryKey: ['batch-analyses', ...analysisIds],
    queryFn: async () => {
      const results = await Promise.allSettled(
        analysisIds.map((id) => getAnalysis(id))
      );
      
      return results.map((result, index) => ({
        id: analysisIds[index],
        status: result.status,
        data: result.status === 'fulfilled' ? result.value : null,
        error: result.status === 'rejected' ? result.reason : null,
      }));
    },
    enabled: analysisIds.length > 0,
    staleTime: 5 * 60 * 1000,
  });
}

/**
 * Hook for analysis metrics/analytics
 * Aggregates data from multiple analyses
 */
export function useAnalysisMetrics() {
  const { analyses } = useAnalysisHistory();
  
  return useQuery({
    queryKey: ['analysis-metrics', analyses.length],
    queryFn: () => {
      if (analyses.length === 0) {
        return {
          total: 0,
          averageConfidence: 0,
          averageProcessingTime: 0,
          statusBreakdown: {},
          successRate: 0,
        };
      }
      
      const total = analyses.length;
      const averageConfidence = 
        analyses.reduce((sum, a) => sum + a.confidence, 0) / total;
      const averageProcessingTime = 
        analyses.reduce((sum, a) => sum + a.processing_time_ms, 0) / total;
      
      const statusBreakdown = analyses.reduce((acc, a) => {
        acc[a.status] = (acc[a.status] || 0) + 1;
        return acc;
      }, {} as Record<string, number>);
      
      const successRate = 
        (statusBreakdown['answer'] || 0) / total * 100;
      
      return {
        total,
        averageConfidence,
        averageProcessingTime,
        statusBreakdown,
        successRate,
      };
    },
    enabled: analyses.length > 0,
    staleTime: 30000, // 30 seconds
  });
}