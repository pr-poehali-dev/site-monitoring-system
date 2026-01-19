import { useEffect, useState } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import Icon from '@/components/ui/icon';

const API_URL = 'https://functions.poehali.dev/0d1dbd15-7762-4fb3-af49-47c960f9828b';

interface LinkFindingLog {
  id: number;
  document_id: number;
  document_number: string;
  document_title: string;
  status: string;
  references_found: number;
  links_created: number;
  not_found_refs: string | null;
  message: string;
  created_at: string;
}

const LinkFindingLogs = () => {
  const [logs, setLogs] = useState<LinkFindingLog[]>([]);
  const [loading, setLoading] = useState(true);
  const [autoRefresh, setAutoRefresh] = useState(true);

  const fetchLogs = async () => {
    try {
      const response = await fetch(`${API_URL}?endpoint=link_finding_logs&limit=50`);
      const data = await response.json();
      setLogs(data.logs || []);
    } catch (error) {
      console.error('Error fetching link finding logs:', error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchLogs();
  }, []);

  useEffect(() => {
    if (!autoRefresh) return;

    const interval = setInterval(() => {
      fetchLogs();
    }, 3000);

    return () => clearInterval(interval);
  }, [autoRefresh]);

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'success':
        return 'text-green-600';
      case 'error':
        return 'text-red-600';
      case 'no_references':
        return 'text-gray-400';
      default:
        return 'text-gray-600';
    }
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'success':
        return 'CheckCircle2';
      case 'error':
        return 'XCircle';
      case 'no_references':
        return 'MinusCircle';
      default:
        return 'Circle';
    }
  };

  if (loading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Логи поиска связей</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-center justify-center py-8">
            <Icon name="Loader2" size={24} className="animate-spin text-gray-400" />
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <div>
            <CardTitle className="flex items-center gap-2">
              <Icon name="FileSearch" size={20} />
              Логи поиска связей
            </CardTitle>
            <CardDescription>
              История обработки документов и найденных связей
            </CardDescription>
          </div>
          <button
            onClick={() => setAutoRefresh(!autoRefresh)}
            className={`px-3 py-1 text-xs rounded ${
              autoRefresh ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-700'
            }`}
          >
            {autoRefresh ? 'Автообновление ВКЛ' : 'Автообновление ВЫКЛ'}
          </button>
        </div>
      </CardHeader>
      <CardContent>
        {logs.length === 0 ? (
          <div className="text-center py-8 text-gray-500">
            <Icon name="FileSearch" size={48} className="mx-auto mb-2 opacity-20" />
            <p>Логов поиска связей пока нет</p>
          </div>
        ) : (
          <div className="space-y-2 max-h-[600px] overflow-y-auto">
            {logs.map((log) => (
              <div
                key={log.id}
                className="p-3 border rounded-lg hover:bg-gray-50 transition-colors"
              >
                <div className="flex items-start gap-3">
                  <Icon
                    name={getStatusIcon(log.status)}
                    size={18}
                    className={`mt-0.5 ${getStatusColor(log.status)}`}
                  />
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1">
                      <span className="font-mono text-sm font-semibold text-gray-900">
                        №{log.document_number}
                      </span>
                      <span className="text-xs text-gray-500">
                        {new Date(log.created_at).toLocaleString('ru-RU')}
                      </span>
                    </div>
                    
                    {log.document_title && (
                      <p className="text-xs text-gray-600 mb-2 truncate">
                        {log.document_title}
                      </p>
                    )}

                    <div className="flex flex-wrap gap-2 mb-2">
                      {log.references_found > 0 && (
                        <span className="text-xs px-2 py-0.5 bg-blue-100 text-blue-700 rounded">
                          {log.references_found} упоминаний
                        </span>
                      )}
                      {log.links_created > 0 && (
                        <span className="text-xs px-2 py-0.5 bg-green-100 text-green-700 rounded">
                          {log.links_created} связей
                        </span>
                      )}
                    </div>

                    {log.message && (
                      <p className="text-xs text-gray-700">{log.message}</p>
                    )}

                    {log.not_found_refs && (
                      <div className="mt-2 p-2 bg-orange-50 border border-orange-200 rounded text-xs">
                        <p className="font-semibold text-orange-800 mb-1">
                          Не найдено в БД:
                        </p>
                        <p className="text-orange-700">{log.not_found_refs}</p>
                      </div>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
};

export default LinkFindingLogs;
