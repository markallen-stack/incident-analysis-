'use client';

import { useState } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Badge } from '@/components/ui/badge';
import { CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Loader2, Send, Plus, X, Upload } from 'lucide-react';
import { toast } from 'sonner';
import { useAnalyzeIncident } from '@/lib/hooks/useAnalysis';
import { AnalysisRequest, AnalysisResponse, analyzeIncident } from '@/lib/api';

interface AnalysisFormProps {
  onAnalysisComplete: (result: AnalysisResponse) => void;
  onAnalysisStart?: () => void;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  onStreamUpdate?:(node:any)=>void
}

export function AnalysisForm({ onAnalysisComplete, onAnalysisStart, onStreamUpdate }: AnalysisFormProps) {
  const [query, setQuery] = useState('');
  const [timestamp, setTimestamp] = useState('');
  const [services, setServices] = useState<string[]>([]);
  const [serviceInput, setServiceInput] = useState('');
  const [logFiles, setLogFiles] = useState<File[]>([]);
  const [screenshotFiles, setScreenshotFiles] = useState<File[]>([]);

  const mutation = useAnalyzeIncident();

const fileToBase64 = (file: File) =>
  new Promise<{ filename: string; content_base64: string }>((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => {
      const base64 = reader.result as string;
      resolve({
        filename: file.name,
        content_base64: base64.split(',')[1], // IMPORTANT
      });
    };
    reader.onerror = reject;
    reader.readAsDataURL(file);
  });


//   const handleSubmit = async (e: React.FormEvent) => {
//   e.preventDefault();

//   if (!query || !timestamp) {
//     toast.error('Missing required fields. Please provide query and timestamp.');
//     return;
//   }

//   // Notify parent that analysis is starting
//   onAnalysisStart?.();

//   const logFilesBase64 = await Promise.all(
//     logFiles.map(fileToBase64)
//   );

//   const dashboardImagesBase64 = await Promise.all(
//     screenshotFiles.map(fileToBase64)
//   );

//   const payload = {
//     query,
//     timestamp,
//     services,
//     log_files_base64: logFilesBase64, // ✅ correct shape
//     dashboard_images: dashboardImagesBase64.map(f => f.content_base64),
//   };

//   mutation.mutate(payload as AnalysisRequest, {
//     onSuccess: (data: AnalysisResponse) => {
//       onAnalysisComplete(data);
//       toast.success('Analysis completed successfully!', {
//         description: `Confidence: ${(data.confidence * 100).toFixed(0)}%`,
//       });
//     },
//     onError: (error: { response?: { data?: { detail?: {msg: string}[] } }; message?: string }) => {
//       let msg = 'Unknown error occurred';

//       if (Array.isArray(error?.response?.data?.detail)) {
//         msg = error.response.data.detail.map((d) => d.msg).join(', ');
//       } else if (error?.message) {
//         msg = error.message;
//       }

//       toast.error(`Analysis failed: ${msg}`, {
//         duration: 7000,
//       });
//       onAnalysisStart?.(); // Reset loading state on error
//     },
//   });
// };

// Inside AnalysisForm component
const handleSubmit = async (e: React.FormEvent) => {
  e.preventDefault();
  onAnalysisStart?.();

  try {
    const logFilesBase64 = await Promise.all(logFiles.map(fileToBase64));
    const dashboardImagesBase64 = await Promise.all(screenshotFiles.map(fileToBase64));

    const payload = {
      query,
      timestamp,
      services,
      log_files_base64: logFilesBase64,
      dashboard_images: dashboardImagesBase64.map(f => f.content_base64),
    };

    // Use the streaming helper instead of the raw mutation.mutate
    const result = await analyzeIncident(
      payload as AnalysisRequest, 
      (update) => {
        // This is the magic part that updates the UI live
        if (update.node) onStreamUpdate?.(update.node);
      }
    );
    console.log(result)

    onAnalysisComplete(result);
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  } catch (error: any) {
    toast.error(`Analysis failed: ${error.message}`);
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    onAnalysisComplete(undefined as any); // Reset loading state
  }
};

  const addService = () => {
    if (serviceInput && !services.includes(serviceInput)) {
      setServices([...services, serviceInput]);
      setServiceInput('');
    }
  };

  const removeService = (service: string) => {
    setServices(services.filter((s) => s !== service));
  };

  const handleLogFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files) {
      const newFiles = Array.from(e.target.files);
      setLogFiles([...logFiles, ...newFiles]);
      e.target.value = '';
    }
  };

  const handleScreenshotChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files) {
      const newFiles = Array.from(e.target.files);
      setScreenshotFiles([...screenshotFiles, ...newFiles]);
      e.target.value = '';
    }
  };

  const removeLogFile = (index: number) => {
    setLogFiles(logFiles.filter((_, i) => i !== index));
  };

  const removeScreenshot = (index: number) => {
    setScreenshotFiles(screenshotFiles.filter((_, i) => i !== index));
  };

  const loadExample = () => {
    setQuery('API outage at 14:32 UTC. Users reporting 500 errors and slow response times.');
    setTimestamp('2024-01-15T14:32:00Z');
    setServices(['api-gateway', 'user-service']);
    setLogFiles([]);
    setScreenshotFiles([]);
    toast.success('Example loaded');
  };

  return (
    <>
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle className="text-xl text-foreground">Analyze Incident</CardTitle>
          <Button
            variant="ghost"
            size="sm"
            onClick={loadExample}
            className="text-muted-foreground hover:text-foreground"
          >
            Load Example
          </Button>
        </div>
      </CardHeader>
      <CardContent>
        <form onSubmit={handleSubmit} className="space-y-4">
          {/* Query */}
          <div className="space-y-2">
            <label className="text-sm font-medium text-foreground">
              Incident Description *
            </label>
            <Textarea
              placeholder="Describe the incident: what happened, when, what symptoms..."
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              className="min-h-[100px] bg-background/50 border-border text-foreground placeholder:text-muted-foreground"
              required
            />
          </div>

          {/* Timestamp */}
          <div className="space-y-2">
            <label className="text-sm font-medium text-foreground">
              Incident Timestamp *
            </label>
            <Input
              type="datetime-local"
              value={timestamp.slice(0, 16)}
              onChange={(e) => setTimestamp(e.target.value ? `${e.target.value}:00Z` : '')}
              className="bg-background/50 border-border text-foreground"
              required
            />
          </div>

          {/* Services */}
          <div className="space-y-2">
            <label className="text-sm font-medium text-foreground">
              Affected Services (Optional)
            </label>
            <div className="flex gap-2">
              <Input
                placeholder="e.g., api-gateway"
                value={serviceInput}
                onChange={(e) => setServiceInput(e.target.value)}
                onKeyPress={(e) => e.key === 'Enter' && (e.preventDefault(), addService())}
                className="bg-background/50 border-border text-foreground placeholder:text-muted-foreground"
              />
              <Button
                type="button"
                onClick={addService}
                variant="outline"
                size="icon"
                className="border-border hover:bg-card"
              >
                <Plus className="w-4 h-4" />
              </Button>
            </div>
            {services.length > 0 && (
              <div className="flex flex-wrap gap-2 mt-2">
                {services.map((service) => (
                  <Badge
                    key={service}
                    variant="secondary"
                    className="bg-blue-500/10 text-blue-400 border-blue-500/20"
                  >
                    {service}
                    <button
                      onClick={() => removeService(service)}
                      className="ml-2 hover:text-blue-300"
                    >
                      <X className="w-3 h-3" />
                    </button>
                  </Badge>
                ))}
              </div>
            )}
          </div>

          {/* Log Files */}
          <div className="space-y-2">
            <label className="text-sm font-medium text-foreground">
              Log Files (Optional)
            </label>
            <div className="flex gap-2">
              <Input
                type="file"
                multiple
                onChange={handleLogFileChange}
                accept=".log,.txt,.json,.csv"
                className="bg-background/50 border-border text-foreground"
              />
              <Button
                type="button"
                variant="outline"
                size="icon"
                disabled={logFiles.length === 0}
                className="border-border hover:bg-card"
              >
                <Upload className="w-4 h-4" />
              </Button>
            </div>
            {logFiles.length > 0 && (
              <div className="flex flex-wrap gap-2 mt-2">
                {logFiles.map((file, index) => (
                  <Badge
                    key={`${file.name}-${index}`}
                    variant="secondary"
                    className="bg-cyan-500/10 text-cyan-400 border-cyan-500/20 max-w-xs"
                  >
                    <span className="truncate">{file.name}</span>
                    <button
                      onClick={() => removeLogFile(index)}
                      className="ml-2 hover:text-cyan-300"
                    >
                      <X className="w-3 h-3" />
                    </button>
                  </Badge>
                ))}
              </div>
            )}
          </div>

          {/* Screenshot Files */}
          <div className="space-y-2">
            <label className="text-sm font-medium text-foreground">
              Dashboard Screenshots (Optional)
            </label>
            <div className="flex gap-2">
              <Input
                type="file"
                multiple
                onChange={handleScreenshotChange}
                accept="image/*"
                className="bg-background/50 border-border text-foreground"
              />
              <Button
                type="button"
                variant="outline"
                size="icon"
                disabled={screenshotFiles.length === 0}
                className="border-border hover:bg-card"
              >
                <Upload className="w-4 h-4" />
              </Button>
            </div>
            {screenshotFiles.length > 0 && (
              <div className="flex flex-wrap gap-2 mt-2">
                {screenshotFiles.map((file, index) => (
                  <Badge
                    key={`${file.name}-${index}`}
                    variant="secondary"
                    className="bg-purple-500/10 text-purple-400 border-purple-500/20 max-w-xs"
                  >
                    <span className="truncate">{file.name}</span>
                    <button
                      onClick={() => removeScreenshot(index)}
                      className="ml-2 hover:text-purple-300"
                    >
                      <X className="w-3 h-3" />
                    </button>
                  </Badge>
                ))}
              </div>
            )}
          </div>

          {/* Submit Button */}
          <Button
            type="submit"
            disabled={mutation.isPending}
            className="w-full  hover:to-cyan-600"
          >
            {mutation.isPending ? (
              <>
                <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                Analyzing...
              </>
            ) : (
              <>
                <Send className="w-4 h-4 mr-2" />
                Analyze Incident
              </>
            )}
          </Button>

          {mutation.isPending && (
            <div className="text-sm text-muted-foreground text-center">
              Running multi-agent analysis...
            </div>
          )}
        </form>
      </CardContent>
    </>
  );
}