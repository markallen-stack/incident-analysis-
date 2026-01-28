'use client';

import { CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Progress } from '@/components/ui/progress';
import { Separator } from '@/components/ui/separator';
import {
  CheckCircle2,
  XCircle,
  AlertCircle,
  Clock,
  TrendingUp,
  FileText,
  Lightbulb,
  Shield,
} from 'lucide-react';
import { AlternativeHypothesis } from '@/domain/analysisResponse/types';
import { AnalysisResponse } from '@/lib/api';

interface AnalysisResultsProps {
  analysis: AnalysisResponse | undefined;
  isLoading?: boolean;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  streamStatus:any
}

export function AnalysisResults({ analysis, isLoading, streamStatus }: AnalysisResultsProps & { streamStatus?: string }) {
  if (isLoading) {
    return (
      <CardContent className="flex flex-col items-center justify-center py-12 text-center">
        <Clock className="w-8 h-8 text-primary animate-spin mb-4" />
        <p className="text-foreground font-medium">Analyzing incident...</p>
        
        {/* Live Status Badge */}
        {streamStatus && (
          <Badge variant="outline" className="mt-4 border-primary/50 text-primary animate-pulse">
            Active Agent: {streamStatus.replace('_', ' ').toUpperCase()}
          </Badge>
        )}
        
        <p className="text-sm text-muted-foreground mt-2">
          {streamStatus === 'log_retriever' ? 'Scanning distributed logs...' : 'Running multi-agent pipeline'}
        </p>
        <Progress value={undefined} className="mt-4 w-full max-w-xs" />
      </CardContent>
    );
  }


  if (!analysis) {
    return (
      <>
        <CardHeader>
          <CardTitle className="text-xl text-foreground">Analysis Results</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex flex-col items-center justify-center py-12 text-center">
            <div className="w-16 h-16 rounded-full bg-card flex items-center justify-center mb-4">
              <FileText className="w-8 h-8 text-muted-foreground" />
            </div>
            <p className="text-muted-foreground">No analysis yet</p>
            <p className="text-sm text-muted-foreground/70 mt-1">
              Fill out the form and click analyze
            </p>
          </div>
        </CardContent>
      </>
    );
  }

  const getStatusIcon = () => {
    switch (analysis.status) {
      case 'answer':
        return <CheckCircle2 className="w-5 h-5 text-green-400" />;
      case 'refuse':
        return <XCircle className="w-5 h-5 text-red-400" />;
      case 'request_more_data':
        return <AlertCircle className="w-5 h-5 text-yellow-400" />;
      default:
        return <FileText className="w-5 h-5 text-muted-foreground" />;
    }
  };

  const getStatusColor = () => {
    switch (analysis.status) {
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

  const getConfidenceColor = () => {
    if (analysis.confidence >= 0.79) return 'bg-green-500';
    if (analysis.confidence >= 0.6) return 'bg-yellow-500';
    return 'bg-red-500';
  };

  return (
    <>
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle className="text-xl text-foreground">Analysis Results</CardTitle>
          <Badge variant="outline" className={getStatusColor()}>
            {getStatusIcon()}
            <span className="ml-2 capitalize">{analysis.status}</span>
          </Badge>
        </div>
      </CardHeader>
      <CardContent className="space-y-6">
        {/* Confidence Score */}
        <div className="space-y-2">
          <div className="flex items-center justify-between text-sm">
            <span className="text-foreground flex items-center gap-2">
              <Shield className="w-4 h-4" />
              Confidence Score
            </span>
            <span className="font-medium text-foreground">
              {(analysis.confidence * 100).toFixed(0)}%
            </span>
          </div>
          <Progress color={getConfidenceColor()} value={analysis.confidence * 100} className="h-2 bg-muted" />
        </div>

        <Separator className="bg-border" />

        {/* Root Cause (if answered) */}
        {analysis.status === 'answer' && analysis.root_cause && (
          <Alert className="bg-green-500/10 border-green-500/20">
            <CheckCircle2 className="h-4 w-4 text-green-400" />
            <AlertDescription className="text-foreground">
              <div className="font-semibold mb-1">Root Cause Identified</div>
              <div className="text-sm">{analysis.root_cause}</div>
            </AlertDescription>
          </Alert>
        )}

        {/* Evidence */}
       {/* Evidence */}
{analysis.evidence && Object.keys(analysis.evidence).length > 0 && (
  <div className="space-y-3">
    <h4 className="text-sm font-semibold text-foreground flex items-center gap-2">
      <FileText className="w-4 h-4" />
      Supporting Evidence
    </h4>
    <div className="space-y-2">
      {Object.entries(analysis.evidence).map(([source, items]) => {
        // Skip empty categories (like your empty metrics/images arrays)
        if (!Array.isArray(items) || items.length === 0) return null;

        return (
          <div
            key={source}
            className="p-3 rounded-lg bg-background/50 border border-border"
          >
            <div className="flex justify-between items-center mb-2">
              <div className="text-xs font-bold text-muted-foreground uppercase">
                {source} ({items.length})
              </div>
            </div>
            <ul className="space-y-2">
              {items.map((item: {source:string,confidence:number}, idx: number) => (
                <li key={idx} className="text-sm text-foreground border-l-2 border-primary/30 pl-3">
                  <div className="text-xs text-muted-foreground/70 flex justify-between">
                    <span>Source: {item.source}</span>
                    <span>Conf: {(item.confidence * 100).toFixed(0)}%</span>
                  </div>
                  {/* Access the content/message from the evidence item */}
                  {/* {item.content || item.metadata?.message || "View details in timeline"} */}
                </li>
              ))}
            </ul>
          </div>
        );
      })}
    </div>
  </div>
)}

        {/* Timeline */}
        {analysis.timeline && (
          <div className="space-y-3">
            <h4 className="text-sm font-semibold text-foreground flex items-center gap-2">
              <Clock className="w-4 h-4" />
              Timeline
            </h4>
            <div className="p-3 rounded-lg bg-background/50 border border-border">
            {analysis.timeline && (
  <div className="space-y-3">
    <h4 className="text-sm font-semibold text-foreground flex items-center gap-2">
      <Clock className="w-4 h-4" /> Timeline
    </h4>
    <div className="relative space-y-4 before:absolute before:inset-0 before:ml-5 before:h-full before:w-0.5 before:bg-border">
      {analysis.timeline.map((item, i) => (
        <div key={i} className="relative flex items-center gap-4 pl-2">
          <div className="absolute left-0 w-10 text-[10px] text-muted-foreground">
             {item.time.split('T')[1]?.substring(0, 5) || '--:--'}
          </div>
          <div className="ml-10 flex-1 p-2 rounded bg-card border border-border text-sm">
            <Badge variant="secondary" className="text-[10px] mb-1">{item.event_type}</Badge>
            <p>{item.event}</p>
          </div>
        </div>
      ))}
    </div>
  </div>
)}
            </div>
          </div>
        )}

        {/* Recommended Actions */}
        {analysis.recommended_actions && analysis.recommended_actions.length > 0 && (
          <div className="space-y-3">
            <h4 className="text-sm font-semibold text-foreground flex items-center gap-2">
              <Lightbulb className="w-4 h-4" />
              Recommended Actions
            </h4>
            <div className="space-y-2">
              {analysis.recommended_actions.map((action: string, index: number) => (
                <div
                  key={index}
                  className="flex items-start gap-3 p-3 rounded-lg bg-blue-500/5 border border-blue-500/10"
                >
                  <div className="w-6 h-6 rounded-full bg-blue-500/10 flex items-center justify-center flex-shrink-0 mt-0.5">
                    <span className="text-xs font-medium text-blue-400">{index + 1}</span>
                  </div>
                  <div className="text-sm text-foreground">{action}</div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Alternative Hypotheses */}
        {analysis.alternative_hypotheses && analysis.alternative_hypotheses.length > 0 && (
          <div className="space-y-3">
            <h4 className="text-sm font-semibold text-foreground flex items-center gap-2">
              <TrendingUp className="w-4 h-4" />
              Alternative Hypotheses
            </h4>
            <div className="space-y-2">
              {analysis.alternative_hypotheses.map((alt: AlternativeHypothesis, index: number) => (
                <div
                  key={index}
                  className="p-3 rounded-lg bg-background/50 border border-border"
                >
                  <div className="text-sm font-medium text-foreground mb-1">
                    {alt.hypothesis}
                  </div>
                  <div className="text-xs text-muted-foreground">
                    Why less likely: {alt.why_less_likely}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Missing Evidence (if refused or needs more data) */}
        {analysis.missing_evidence && analysis.missing_evidence.length > 0 && (
          <Alert className="bg-yellow-500/10 border-yellow-500/20">
            <AlertCircle className="h-4 w-4 text-yellow-400" />
            <AlertDescription>
              <div className="font-semibold text-yellow-400 mb-2">Missing Evidence</div>
              <ul className="text-sm text-foreground space-y-1">
                {analysis.missing_evidence.map((item: string, index: number) => (
                  <li key={index} className="flex items-start gap-2">
                    <span className="text-yellow-400">•</span>
                    <span>{item}</span>
                  </li>
                ))}
              </ul>
            </AlertDescription>
          </Alert>
        )}

        {/* Processing Stats */}
        <div className="pt-4 border-t border-border">
          <div className="grid grid-cols-2 gap-4 text-sm">
            <div>
              <div className="text-muted-foreground">Analysis ID</div>
              <div className="text-foreground font-mono text-xs">
                {analysis.analysis_id}
              </div>
            </div>
            <div>
              <div className="text-muted-foreground">Processing Time</div>
              <div className="text-foreground">
                {analysis.processing_time_ms.toFixed(0)}ms
              </div>
            </div>
          </div>
        </div>
      </CardContent>
    </>
  );
}