'use client';

import { useState, useEffect } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Loader2, Save, Key, Cpu, Target, Gauge, FileText, FolderOpen } from 'lucide-react';
import { useSettings, useUpdateSettings } from '@/lib/hooks/useAnalysis';
import type { SettingSchema } from '@/lib/api';

const CATEGORY_ICONS: Record<string, React.ReactNode> = {
  api_keys: <Key className="w-4 h-4" />,
  models: <Cpu className="w-4 h-4" />,
  thresholds: <Target className="w-4 h-4" />,
  observability: <Gauge className="w-4 h-4" />,
  performance: <Cpu className="w-4 h-4" />,
  logging: <FileText className="w-4 h-4" />,
  paths: <FolderOpen className="w-4 h-4" />,
};

const CATEGORY_LABELS: Record<string, string> = {
  api_keys: 'API Keys',
  models: 'Models',
  thresholds: 'Thresholds',
  observability: 'Observability',
  logging: 'Logging',
  performance: 'Performance',
  paths: 'Paths',
};

export function Settings() {
  const { data, isLoading, isError } = useSettings();
  const mutation = useUpdateSettings();
  const [formValues, setFormValues] = useState<Record<string, string | number | boolean>>({});

  useEffect(() => {
    if (data?.values && typeof data.values === 'object') {
      setFormValues({ ...data.values } as Record<string, string | number | boolean>);
    }
  }, [data?.values]);

  const handleChange = (key: string, value: string | number | boolean) => {
    setFormValues((prev) => ({ ...prev, [key]: value }));
  };

  const handleSave = () => {
    mutation.mutate(formValues, {
      onSuccess: () => {
        // Success feedback is handled by the hook's toast
      },
      onError: (error: any) => {
        // Error feedback is handled by the hook's toast
      },
    });
  };

  if (isLoading || !data) {
    return (
      <Card className="bg-card/50 border-border backdrop-blur-sm">
        <CardContent className="flex items-center justify-center py-16">
          <Loader2 className="w-8 h-8 animate-spin text-muted-foreground" />
        </CardContent>
      </Card>
    );
  }

  if (isError) {
    return (
      <Card className="bg-card/50 border-border backdrop-blur-sm">
        <CardContent className="py-8 text-center text-muted-foreground">
          Failed to load settings. Check that the API is running.
        </CardContent>
      </Card>
    );
  }

  const schema = (data.schema || []) as SettingSchema[];
  const byCategory = schema.reduce<Record<string, SettingSchema[]>>((acc, s) => {
    const c = s.category || 'other';
    if (!acc[c]) acc[c] = [];
    acc[c].push(s);
    return acc;
  }, {});

  const categoryOrder = ['api_keys', 'models', 'thresholds', 'observability', 'performance', 'logging', 'paths'];
  const sortedCategories = categoryOrder.filter((c) => byCategory[c]?.length);

  return (
    <Card className="bg-card/50 border-border backdrop-blur-sm">
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle className="text-xl text-foreground">Settings</CardTitle>
          <Button
            onClick={handleSave}
            disabled={mutation.isPending || mutation.isSuccess}
            className="border-border hover:bg-card"
          >
            {mutation.isPending ? (
              <>
                <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                Saving...
              </>
            ) : mutation.isSuccess ? (
              <>
                <Save className="w-4 h-4 mr-2 text-green-500" />
                Saved!
              </>
            ) : (
              <>
                <Save className="w-4 h-4 mr-2" />
                Save
              </>
            )}
          </Button>
        </div>
        <p className="text-sm text-muted-foreground mt-1">
          Backend configuration. Changes take effect immediately for most settings.
        </p>
      </CardHeader>
      <CardContent className="space-y-8">
        {sortedCategories.map((cat) => (
          <section key={cat} className="space-y-4">
            <h3 className="text-sm font-semibold text-foreground flex items-center gap-2">
              {CATEGORY_ICONS[cat] || <FolderOpen className="w-4 h-4" />}
              {CATEGORY_LABELS[cat] || cat}
            </h3>
            <div className="grid gap-4 sm:grid-cols-1 lg:grid-cols-2">
              {byCategory[cat].map((s) => {
                const val = formValues[s.key];
                const isSecret = !!s.secret;
                const isBool = s.type === 'bool';

                return (
                  <div key={s.key} className="space-y-1.5">
                    <label className="text-sm font-medium text-foreground">{s.label}</label>
                    {s.description && (
                      <p className="text-xs text-muted-foreground">{s.description}</p>
                    )}
                    {isBool ? (
                      <div className="flex items-center gap-2 h-9">
                        <input
                          type="checkbox"
                          checked={!!val}
                          onChange={(e) => handleChange(s.key, e.target.checked)}
                          className="h-4 w-4 rounded border-border bg-background/50 text-foreground"
                        />
                        <span className="text-sm text-muted-foreground">
                          {val ? 'On' : 'Off'}
                        </span>
                      </div>
                    ) : (
                      <Input
                        type={isSecret ? 'password' : s.type === 'int' || s.type === 'float' ? 'number' : 'text'}
                        value={val !== undefined && val !== null ? String(val) : ''}
                        onChange={(e) => {
                          const v = e.target.value;
                          if (s.type === 'int') handleChange(s.key, v === '' ? 0 : parseInt(v, 10));
                          else if (s.type === 'float') handleChange(s.key, v === '' ? 0 : parseFloat(v));
                          else handleChange(s.key, v);
                        }}
                        placeholder={isSecret ? '••••••••' : undefined}
                        className="bg-background/50 border-border text-foreground placeholder:text-muted-foreground"
                        step={s.type === 'float' ? 'any' : undefined}
                      />
                    )}
                  </div>
                );
              })}
            </div>
          </section>
        ))}
      </CardContent>
    </Card>
  );
}
