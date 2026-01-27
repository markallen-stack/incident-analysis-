'use client';

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import { 
  useStats, 
  useAnalysisMetrics, 
  useAnalysisHistory 
} from '@/lib/hooks/useAnalysis';
import { 
  Activity, 
  TrendingUp, 
  Clock, 
  CheckCircle2, 
  XCircle,
  AlertCircle,
  BarChart3 
} from 'lucide-react';
import { 
  BarChart, 
  Bar, 
  XAxis, 
  YAxis, 
  CartesianGrid, 
  Tooltip, 
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
  Legend
} from 'recharts';

export function AnalyticsDashboard() {
  const { data: apiStats, isLoading: statsLoading } = useStats();
  const { data: metrics, isLoading: metricsLoading } = useAnalysisMetrics();
  const { analyses } = useAnalysisHistory();

  if (statsLoading || metricsLoading) {
    return <AnalyticsSkeleton />;
  }

  // Prepare chart data
  const statusData = metrics?.statusBreakdown ? [
    { name: 'Answer', value: metrics.statusBreakdown['answer'] || 0, color: '#10b981' },
    { name: 'Refuse', value: metrics.statusBreakdown['refuse'] || 0, color: '#ef4444' },
    { name: 'Need Data', value: metrics.statusBreakdown['request_more_data'] || 0, color: '#f59e0b' },
  ] : [];

  const confidenceData = analyses.map((a, i) => ({
    index: i + 1,
    confidence: a.confidence * 100,
    status: a.status,
  })).slice(0, 10).reverse();

  return (
    <div className="space-y-6">
      {/* Stats Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          title="Total Analyses"
          value={metrics?.total || 0}
          icon={<Activity className="w-4 h-4" />}
          trend={`${apiStats?.total_analyses || 0} cached`}
        />
        
        <StatCard
          title="Success Rate"
          value={`${metrics?.successRate.toFixed(1) || 0}%`}
          icon={<TrendingUp className="w-4 h-4" />}
          trend="Answer rate"
          color="text-green-400"
        />
        
        <StatCard
          title="Avg Confidence"
          value={`${((metrics?.averageConfidence || 0) * 100).toFixed(0)}%`}
          icon={<CheckCircle2 className="w-4 h-4" />}
          trend="Overall average"
          color="text-blue-400"
        />
        
        <StatCard
          title="Avg Time"
          value={`${(metrics?.averageProcessingTime || 0).toFixed(0)}ms`}
          icon={<Clock className="w-4 h-4" />}
          trend="Processing time"
          color="text-cyan-400"
        />
      </div>

      {/* Charts */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Status Distribution */}
        <Card className="bg-card/50 border-border">
          <CardHeader>
            <CardTitle className="text-lg text-foreground flex items-center gap-2">
              <BarChart3 className="w-5 h-5" />
              Status Distribution
            </CardTitle>
          </CardHeader>
          <CardContent>
            {statusData.length > 0 ? (
              <ResponsiveContainer width="100%" height={250}>
                <PieChart>
                  <Pie
                    data={statusData}
                    cx="50%"
                    cy="50%"
                    labelLine={false}
                    label={({ name, percent }) => `${name} ${(percent||0 * 100).toFixed(0)}%`}
                    outerRadius={80}
                    fill="#8884d8"
                    dataKey="value"
                  >
                    {statusData.map((entry, index) => (
                      <Cell key={`cell-${index}`} fill={entry.color} />
                    ))}
                  </Pie>
                  <Tooltip 
                    contentStyle={{ 
                      backgroundColor: '#1e293b', 
                      border: '1px solid #334155',
                      borderRadius: '8px'
                    }}
                  />
                  <Legend />
                </PieChart>
              </ResponsiveContainer>
            ) : (
              <div className="h-[250px] flex items-center justify-center text-muted-foreground">
                No data yet
              </div>
            )}
          </CardContent>
        </Card>

        {/* Confidence Trend */}
        <Card className="bg-card/50 border-border">
          <CardHeader>
            <CardTitle className="text-lg text-foreground flex items-center gap-2">
              <TrendingUp className="w-5 h-5" />
              Confidence Trend
            </CardTitle>
          </CardHeader>
          <CardContent>
            {confidenceData.length > 0 ? (
              <ResponsiveContainer width="100%" height={250}>
                <BarChart data={confidenceData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--muted))/0.3" />
                  <XAxis 
                    dataKey="index" 
                    stroke="hsl(var(--muted-foreground))"
                    label={{ value: 'Analysis #', position: 'insideBottom', offset: -5 }}
                  />
                  <YAxis 
                    stroke="hsl(var(--muted-foreground))"
                    label={{ value: 'Confidence %', angle: -90, position: 'insideLeft' }}
                  />
                  <Tooltip 
                    contentStyle={{ 
                      backgroundColor: 'hsl(var(--background))', 
                      border: '1px solid hsl(var(--border))',
                      borderRadius: '8px'
                    }}
                  />
                  <Bar dataKey="confidence" fill="#3b82f6" radius={[8, 8, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <div className="h-[250px] flex items-center justify-center text-muted-foreground">
                No data yet
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Recent Activity */}
      <Card className="bg-card/50 border-border">
        <CardHeader>
          <CardTitle className="text-lg text-foreground">Recent Analyses</CardTitle>
        </CardHeader>
        <CardContent>
          {analyses.length > 0 ? (
            <div className="space-y-3">
              {analyses.slice(0, 5).map((analysis) => (
                <div
                  key={analysis.analysis_id}
                  className="flex items-center justify-between p-3 rounded-lg bg-background/50 border border-border"
                >
                  <div className="flex items-center gap-3">
                    {getStatusIcon(analysis.status)}
                    <div>
                      <div className="text-sm font-medium text-foreground">
                        {analysis.root_cause || 'Analysis completed'}
                      </div>
                      <div className="text-xs text-muted-foreground">
                        {analysis.analysis_id}
                      </div>
                    </div>
                  </div>
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
              ))}
            </div>
          ) : (
            <div className="text-center py-8 text-muted-foreground">
              No analyses yet
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

function StatCard({ 
  title, 
  value, 
  icon, 
  trend, 
  color = 'text-muted-foreground' 
}: { 
  title: string; 
  value: string | number; 
  icon: React.ReactNode; 
  trend?: string;
  color?: string;
}) {
  return (
    <Card className="bg-card/50 border-border">
      <CardContent className="p-6">
        <div className="flex items-center justify-between mb-2">
          <span className="text-sm text-muted-foreground">{title}</span>
          <div className={color}>{icon}</div>
        </div>
        <div className="text-2xl font-bold text-foreground mb-1">{value}</div>
        {trend && <div className="text-xs text-muted-foreground/70">{trend}</div>}
      </CardContent>
    </Card>
  );
}

function AnalyticsSkeleton() {
  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {[...Array(4)].map((_, i) => (
          <Card key={i} className="bg-card/50 border-border">
            <CardContent className="p-6">
              <Skeleton className="h-4 w-24 mb-4 bg-muted" />
              <Skeleton className="h-8 w-16 mb-2 bg-muted" />
              <Skeleton className="h-3 w-20 bg-muted" />
            </CardContent>
          </Card>
        ))}
      </div>
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {[...Array(2)].map((_, i) => (
          <Card key={i} className="bg-card/50 border-border">
            <CardContent className="p-6">
              <Skeleton className="h-[250px] w-full bg-muted" />
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}

function getStatusIcon(status: string) {
  switch (status) {
    case 'answer':
      return <CheckCircle2 className="w-5 h-5 text-green-400" />;
    case 'refuse':
      return <XCircle className="w-5 h-5 text-red-400" />;
    case 'request_more_data':
      return <AlertCircle className="w-5 h-5 text-yellow-400" />;
    default:
      return <Activity className="w-5 h-5 text-muted-foreground" />;
  }
}