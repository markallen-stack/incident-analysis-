'use client';

import { useState } from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { AnalysisForm } from '@/components/AnalysisForm';
import { AnalysisResults } from '@/components/AnalysisResults';
import { History } from '@/components/History';
import { AnalyticsDashboard } from '@/components/AnalyticsDashboard';
import { ApiStatus } from '@/components/ApiStatus';
import { Settings } from '@/components/Settings';
import { Login } from '@/components/Login';
import { ThemeToggle } from '@/components/theme-toggle';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Activity, History as HistoryIcon, BarChart3, Settings as SettingsIcon, LogOut, User } from 'lucide-react';
import { Toaster } from 'sonner';
import { AnalysisResponse } from '@/lib/api';
import { useAuth, useLogout } from '@/lib/hooks/useAuth';

const queryClient = new QueryClient();



function AppContent() {
  const [currentAnalysis, setCurrentAnalysis] = useState<AnalysisResponse>();
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const { user, isAuthenticated } = useAuth();
  const logout = useLogout();

  const handleAnalysisComplete = (result: AnalysisResponse) => {
    setCurrentAnalysis(result);
    setIsAnalyzing(false);
  };

  const handleAnalysisStart = () => {
    setIsAnalyzing(true);
    setCurrentAnalysis(undefined);
  };

  // Show login if not authenticated
  if (!isAuthenticated) {
    return <Login />;
  }

  return (
    <main className="min-h-screen bg-background">
      {/* Header */}
      <div className="border-b border-border bg-background backdrop-blur-xl">
        <div className="container mx-auto px-4 py-6">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-3xl font-bold text-foreground">
                Incident Analysis System
              </h1>
              <p className="text-muted-foreground mt-1">
                AI-powered root cause analysis with multi-agent verification
              </p>
            </div>
            <div className="flex items-center gap-3">
              {user && (
                <div className="flex items-center gap-2 text-sm text-muted-foreground">
                  <User className="w-4 h-4" />
                  <span>{user.name || user.email}</span>
                </div>
              )}
              <Button variant="outline" size="sm" onClick={logout}>
                <LogOut className="w-4 h-4 mr-2" />
                Logout
              </Button>
              <ThemeToggle />
              <ApiStatus />
            </div>
          </div>
        </div>
      </div>

        <div className="container mx-auto px-4 py-8">
          <Tabs defaultValue="analyze" className="space-y-6">
            <TabsList className="bg-card/50 border border-border">
              <TabsTrigger value="analyze" className="data-[state=active]:bg-card">
                <Activity className="w-4 h-4 mr-2 text-foreground" />
                <p className='text-foreground'>Analyze</p>
              </TabsTrigger>
              <TabsTrigger value="history" className="data-[state=active]:bg-card">
                <HistoryIcon className="w-4 h-4 mr-2 text-foreground" />
                <p className='text-foreground'>
                History
                </p>
              </TabsTrigger>
              <TabsTrigger value="analytics" className="data-[state=active]:bg-card">
                <BarChart3 className="w-4 h-4 mr-2 text-foreground" />
                <p className='text-foreground'>Analytics</p>
              </TabsTrigger>
              <TabsTrigger value="settings" className="data-[state=active]:bg-card">
                <SettingsIcon className="w-4 h-4 mr-2 text-foreground" />
                <p className='text-foreground'>Settings</p>
              </TabsTrigger>
            </TabsList>

            <TabsContent value="analyze" className="space-y-6">
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                {/* Analysis Form */}
                <Card className="bg-card/50 border-border backdrop-blur-sm">
                  <AnalysisForm 
                    onAnalysisComplete={handleAnalysisComplete}
                    onAnalysisStart={handleAnalysisStart}
                  />
                </Card>

                {/* Results */}
                <Card className="bg-card/50 border-border backdrop-blur-sm">
                  <AnalysisResults 
                    analysis={currentAnalysis} 
                    isLoading={isAnalyzing}
                  />
                </Card>
              </div>
            </TabsContent>

            <TabsContent value="history">
              <History />
            </TabsContent>

            <TabsContent value="analytics">
              <AnalyticsDashboard />
            </TabsContent>

            <TabsContent value="settings">
              <Settings />
            </TabsContent>
          </Tabs>
        </div>

        <Toaster position="top-right" theme="dark" />
      </main>
    );
}

export default function Home() {
  return (
    <QueryClientProvider client={queryClient}>
      <AppContent />
    </QueryClientProvider>
  );
}