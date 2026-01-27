'use client';

import { Badge } from '@/components/ui/badge';
import { CheckCircle2, XCircle, Loader2 } from 'lucide-react';
import { useHealth } from '@/lib/hooks/useAnalysis';

export function ApiStatus() {
  const { data, isLoading, isError } = useHealth();

  if (isLoading) {
    return (
      <Badge variant="outline" className="bg-background/50 border-border">
        <Loader2 className="w-3 h-3 mr-2 animate-spin" />
        <span className="text-muted-foreground">Connecting...</span>
      </Badge>
    );
  }

  if (isError || !data) {
    return (
      <Badge variant="outline" className="bg-red-500/10 border-red-500/20">
        <XCircle className="w-3 h-3 mr-2 text-red-400" />
        <span className="text-red-400">API Offline</span>
      </Badge>
    );
  }

  return (
    <div className="flex items-center gap-3">
      <Badge variant="outline" className="bg-green-500/10 border-green-500/20">
        <CheckCircle2 className="w-3 h-3 mr-2 text-green-400" />
        <span className="text-green-400">API Online</span>
      </Badge>
      
      {data.mcp_enabled && data.mcp_servers.length > 0 && (
        <Badge variant="outline" className="bg-blue-500/10 border-blue-500/20">
          <span className="text-blue-400">
            MCP: {data.mcp_servers.join(', ')}
          </span>
        </Badge>
      )}
    </div>
  );
}