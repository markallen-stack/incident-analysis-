'use client';

import { CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { ScrollArea } from '@/components/ui/scroll-area';
import { formatDistanceToNow } from 'date-fns';
import { Clock, CheckCircle2, XCircle, AlertCircle, ChevronRight } from 'lucide-react';
import { IncidentAnalysis } from '@/domain/analysisResponse/types';
import { AnalysisResponse } from '@/lib/api';

interface AnalysisHistoryProps {
  history: AnalysisResponse[];
  onSelectAnalysis: (analysis: AnalysisResponse) => void;
}

export function AnalysisHistory({ history, onSelectAnalysis }: AnalysisHistoryProps) {
  if (history.length === 0) {
    return (
      <>
        <CardHeader>
          <CardTitle className="text-xl text-foreground">Analysis History</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex flex-col items-center justify-center py-12 text-center">
            <div className="w-16 h-16 rounded-full bg-card flex items-center justify-center mb-4">
              <Clock className="w-8 h-8 text-muted-foreground" />
            </div>
            <p className="text-muted-foreground">No analysis history yet</p>
            <p className="text-sm text-muted-foreground/70 mt-1">
              Your completed analyses will appear here
            </p>
          </div>
        </CardContent>
      </>
    );
  }

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'answer':
        return <CheckCircle2 className="w-4 h-4 text-green-400" />;
      case 'refuse':
        return <XCircle className="w-4 h-4 text-red-400" />;
      case 'request_more_data':
        return <AlertCircle className="w-4 h-4 text-yellow-400" />;
      default:
        return null;
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'answer':
        return 'bg-green-500/10 text-green-400 border-green-500/20';
      case 'refuse':
        return 'bg-red-500/10 text-red-400 border-red-500/20';
      case 'request_more_data':
        return 'bg-yellow-500/10 text-yellow-400 border-yellow-500/20';
      default:
        return 'bg-muted text-muted-foreground border-border';
    }
  };

  return (
    <>
      <CardHeader>
        <CardTitle className="text-xl text-foreground">
          Analysis History ({history.length})
        </CardTitle>
      </CardHeader>
      <CardContent>
        <ScrollArea className="h-[600px] pr-4">
          <div className="space-y-3">
            {history.map((analysis, index) => (
              <div
                key={analysis.analysis_id}
                className="group p-4 rounded-lg bg-background/50 border border-border hover:border-muted-foreground/20 transition-colors cursor-pointer"
                onClick={() => onSelectAnalysis(analysis)}
              >
                <div className="flex items-start justify-between mb-3">
                  <div className="flex items-center gap-2">
                    <Badge variant="outline" className={getStatusColor(analysis.status)}>
                      {getStatusIcon(analysis.status)}
                      <span className="ml-1 capitalize text-xs">{analysis.status}</span>
                    </Badge>
                    <span className="text-xs text-muted-foreground/70">
                      {formatDistanceToNow(new Date(parseInt(analysis.analysis_id.split('_')[1])), {
                        addSuffix: true,
                      })}
                    </span>
                  </div>
                  <ChevronRight className="w-4 h-4 text-muted-foreground/50 group-hover:text-muted-foreground transition-colors" />
                </div>

                <div className="space-y-2">
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-medium text-muted-foreground">Confidence:</span>
                    <Badge
                      variant="outline"
                      className={
                        analysis.confidence >= 0.7
                          ? 'bg-green-500/10 text-green-400 border-green-500/20'
                          : 'bg-yellow-500/10 text-yellow-400 border-yellow-500/20'
                      }
                    >
                      {(analysis.confidence * 100).toFixed(0)}%
                    </Badge>
                  </div>

                  {analysis.root_cause && (
                    <p className="text-sm text-foreground line-clamp-2">
                      {analysis.root_cause}
                    </p>
                  )}

                  <div className="flex items-center gap-2 text-xs text-muted-foreground/70">
                    <Clock className="w-3 h-3" />
                    {analysis.processing_time_ms.toFixed(0)}ms
                  </div>
                </div>
              </div>
            ))}
          </div>
        </ScrollArea>
      </CardContent>
    </>
  );
}