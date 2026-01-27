'use client';

import { useState } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from './ui/card';
import { Button } from './ui/button';
import { Badge } from './ui/badge';
import { useAnalysisHistory, useDeleteAnalysis } from '../lib/hooks/useHistory';
import { AnalysisSummary } from '../lib/api';
import { format } from 'date-fns';
import { Trash2, Eye, Loader2, AlertCircle, RefreshCw } from 'lucide-react';
import { useRouter } from 'next/navigation';
import { toast } from 'sonner';

export function History() {
  const [page, setPage] = useState(0);
  const [statusFilter, setStatusFilter] = useState<string | undefined>(undefined);
  const limit = 20;
  const offset = page * limit;

  const { data, isLoading, error } = useAnalysisHistory(limit, offset, statusFilter);
  const deleteMutation = useDeleteAnalysis();
  const router = useRouter();

  const handleDelete = async (analysisId: string) => {
    if (confirm('Are you sure you want to delete this analysis?')) {
      deleteMutation.mutate(analysisId, {
        onSuccess: () => {
          toast.success('Analysis deleted successfully');
        },
        onError: (error: any) => {
          toast.error(error.response?.data?.detail || 'Failed to delete analysis');
        },
      });
    }
  };

  const handleView = (analysisId: string) => {
    router.push(`/analysis/${analysisId}`);
  };

  if (isLoading) {
    return (
      <Card className="bg-card/50 border-border backdrop-blur-sm">
        <CardHeader>
          <CardTitle>Analysis History</CardTitle>
          <CardDescription>Loading your analysis history...</CardDescription>
        </CardHeader>
        <CardContent className="flex items-center justify-center py-16">
          <div className="flex flex-col items-center gap-3">
            <Loader2 className="w-8 h-8 animate-spin text-muted-foreground" />
            <p className="text-sm text-muted-foreground">Fetching your analyses...</p>
          </div>
        </CardContent>
      </Card>
    );
  }

  if (error) {
    return (
      <Card className="bg-card/50 border-border backdrop-blur-sm">
        <CardHeader>
          <CardTitle>Analysis History</CardTitle>
          <CardDescription>Error loading history</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex flex-col items-center gap-4 py-8">
            <div className="flex items-center gap-2 text-red-500">
              <AlertCircle className="w-5 h-5" />
              <p className="text-sm">{(error as Error).message}</p>
            </div>
            <Button
              variant="outline"
              onClick={() => window.location.reload()}
              className="flex items-center gap-2"
            >
              <RefreshCw className="w-4 h-4" />
              Retry
            </Button>
          </div>
        </CardContent>
      </Card>
    );
  }

  const analyses = data?.analyses || [];
  const total = data?.total || 0;
  const totalPages = Math.ceil(total / limit);

  return (
    <Card className="bg-card/50 border-border backdrop-blur-sm">
      <CardHeader>
        <CardTitle>Analysis History</CardTitle>
        <CardDescription>
          {total} {total === 1 ? 'analysis' : 'analyses'} found
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Status Filter */}
        <div className="flex gap-2">
          <Button
            variant={statusFilter === undefined ? 'default' : 'outline'}
            size="sm"
            onClick={() => setStatusFilter(undefined)}
          >
            All
          </Button>
          <Button
            variant={statusFilter === 'answer' ? 'default' : 'outline'}
            size="sm"
            onClick={() => setStatusFilter('answer')}
          >
            Answered
          </Button>
          <Button
            variant={statusFilter === 'refuse' ? 'default' : 'outline'}
            size="sm"
            onClick={() => setStatusFilter('refuse')}
          >
            Refused
          </Button>
          <Button
            variant={statusFilter === 'request_more_data' ? 'default' : 'outline'}
            size="sm"
            onClick={() => setStatusFilter('request_more_data')}
          >
            Need More Data
          </Button>
        </div>

        {/* Analysis List */}
        {analyses.length === 0 ? (
          <p className="text-muted-foreground text-center py-8">
            No analyses found. Run your first analysis to see it here!
          </p>
        ) : (
          <div className="space-y-2">
            {analyses.map((analysis: AnalysisSummary) => (
              <div
                key={analysis.id}
                className="flex items-center justify-between p-4 border rounded-lg hover:bg-accent/50 transition-colors"
              >
                <div className="flex-1">
                  <div className="flex items-center gap-2 mb-1">
                    <span className="font-mono text-sm text-muted-foreground">
                      {analysis.analysis_id}
                    </span>
                    <Badge
                      variant={
                        analysis.status === 'answer'
                          ? 'default'
                          : analysis.status === 'refuse'
                          ? 'destructive'
                          : 'secondary'
                      }
                    >
                      {analysis.status}
                    </Badge>
                    <Badge variant="outline">
                      {(analysis.confidence * 100).toFixed(0)}% confidence
                    </Badge>
                  </div>
                  {analysis.root_cause && (
                    <p className="text-sm text-muted-foreground line-clamp-1">
                      {analysis.root_cause}
                    </p>
                  )}
                  <p className="text-xs text-muted-foreground mt-1">
                    {format(new Date(analysis.created_at), 'PPp')} •{' '}
                    {(analysis.processing_time_ms / 1000).toFixed(1)}s
                  </p>
                </div>
                <div className="flex gap-2 ml-4">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => handleView(analysis.analysis_id)}
                  >
                    <Eye className="h-4 w-4 mr-1" />
                    View
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => handleDelete(analysis.analysis_id)}
                    disabled={deleteMutation.isPending}
                    title="Delete analysis"
                  >
                    {deleteMutation.isPending ? (
                      <Loader2 className="h-4 w-4 animate-spin" />
                    ) : (
                      <Trash2 className="h-4 w-4" />
                    )}
                  </Button>
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Pagination */}
        {totalPages > 1 && (
          <div className="flex items-center justify-between pt-4">
            <Button
              variant="outline"
              onClick={() => setPage((p) => Math.max(0, p - 1))}
              disabled={page === 0}
            >
              Previous
            </Button>
            <span className="text-sm text-muted-foreground">
              Page {page + 1} of {totalPages}
            </span>
            <Button
              variant="outline"
              onClick={() => setPage((p) => Math.min(totalPages - 1, p + 1))}
              disabled={page >= totalPages - 1}
            >
              Next
            </Button>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
