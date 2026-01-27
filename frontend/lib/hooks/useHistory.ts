/**
 * Hooks for analysis history
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { getAnalysisHistory, getAnalysisDetail, deleteAnalysis, AnalysisListResponse, AnalysisSummary } from '../api';
import { toast } from 'sonner';

export const historyKeys = {
  all: ['history'] as const,
  lists: () => [...historyKeys.all, 'list'] as const,
  list: (limit: number, offset: number, status?: string) => [...historyKeys.lists(), limit, offset, status] as const,
  details: () => [...historyKeys.all, 'detail'] as const,
  detail: (id: string) => [...historyKeys.details(), id] as const,
};

/**
 * Hook to get analysis history list
 */
export function useAnalysisHistory(limit: number = 100, offset: number = 0, status?: string) {
  return useQuery({
    queryKey: historyKeys.list(limit, offset, status),
    queryFn: () => getAnalysisHistory(limit, offset, status),
    staleTime: 30 * 1000, // 30 seconds
  });
}

/**
 * Hook to get a specific analysis detail
 */
export function useAnalysisDetail(analysisId: string, enabled: boolean = true) {
  return useQuery({
    queryKey: historyKeys.detail(analysisId),
    queryFn: () => getAnalysisDetail(analysisId),
    enabled: enabled && !!analysisId,
    staleTime: 5 * 60 * 1000, // 5 minutes
  });
}

/**
 * Hook to delete an analysis
 */
export function useDeleteAnalysis() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (analysisId: string) => deleteAnalysis(analysisId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: historyKeys.lists() });
      toast.success('Analysis deleted');
    },
    onError: (error: any) => {
      toast.error(error.response?.data?.detail || 'Failed to delete analysis');
    },
  });
}
